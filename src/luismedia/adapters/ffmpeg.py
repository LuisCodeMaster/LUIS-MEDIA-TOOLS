"""Adapter do FFmpeg/ffprobe: o ponto unico de falha mais grave do projeto antigo.

O que muda em relacao ao `& ffmpeg ...` solto no PowerShell:
- codigo de saida SEMPRE verificado; stderr guardado (ultimas linhas) no erro;
- timeout total + watchdog de travamento (sem progresso por N segundos => mata);
- mata a arvore de processos (Windows e POSIX), sem ffmpeg zumbi segurando arquivo;
- progresso real via ``-progress pipe:1`` (percentual para GUI/API/webhook);
- escreve em arquivo temporario e so renomeia quando deu certo (nada de MP4 pela metade
  que o "if (-not (Test-Path ...))" do script antigo confundia com resultado pronto);
- lista de argumentos, nunca string de shell (fim do Invoke-Expression com nome de arquivo).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path

from ..core.config import Encoder
from ..core.errors import DependencyMissing, InvalidMedia, ProcessFailed, ProcessTimeout
from ..core.logging import get_logger
from ..core.models import MediaInfo

log = get_logger("ffmpeg")
ProgressFn = Callable[[float], None]  # recebe 0.0 .. 1.0


def find_binary(name: str) -> str:
    """Procura primeiro o binario empacotado junto do app, depois o PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    bundled_dirs = [
        os.environ.get("LUISMEDIA_FFMPEG_DIR"),
        Path(getattr(sys, "_MEIPASS", "")) / "bin" if hasattr(sys, "_MEIPASS") else None,
        Path(sys.executable).parent / "bin",
    ]
    for d in filter(None, bundled_dirs):
        candidate = Path(d) / exe
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if not found:
        raise DependencyMissing(f"{name} nao encontrado (nem empacotado, nem no PATH)")
    return found


def _kill_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()
    proc.wait(timeout=10)


def run_ffmpeg(
    args: Sequence[str],
    *,
    duration_hint: float | None = None,
    timeout_s: float | None = None,
    stall_timeout_s: float = 120.0,
    on_progress: ProgressFn | None = None,
    threads: int = 0,
    cancel: threading.Event | None = None,
    cwd: Path | None = None,
) -> None:
    """Executa ffmpeg com watchdog. ``args`` NAO inclui o binario nem -progress."""
    cmd = [find_binary("ffmpeg"), "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
           "-progress", "pipe:1", "-nostats"]
    if threads:
        cmd += ["-threads", str(threads)]
    cmd += list(args)

    popen_kw: dict = {}
    if sys.platform == "win32":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        popen_kw["start_new_session"] = True

    started = time.monotonic()
    last_activity = [started]
    stderr_tail: deque[str] = deque(maxlen=40)

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", cwd=cwd, **popen_kw,
    )

    def _read_progress() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            last_activity[0] = time.monotonic()
            key, _, value = line.strip().partition("=")
            if key == "out_time_us" and duration_hint and on_progress and value.isdigit():
                on_progress(min(1.0, int(value) / 1e6 / duration_hint))

    def _read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_tail.append(line.rstrip())

    readers = [threading.Thread(target=f, daemon=True) for f in (_read_progress, _read_stderr)]
    for t in readers:
        t.start()

    try:
        while proc.poll() is None:
            time.sleep(0.25)
            now = time.monotonic()
            if cancel is not None and cancel.is_set():
                _kill_tree(proc)
                raise ProcessTimeout("cancelado pelo usuario")
            if timeout_s and now - started > timeout_s:
                _kill_tree(proc)
                raise ProcessTimeout(f"ffmpeg passou de {timeout_s:.0f}s", detail="\n".join(stderr_tail))
            if now - last_activity[0] > stall_timeout_s:
                _kill_tree(proc)
                raise ProcessTimeout(
                    f"ffmpeg sem progresso ha {stall_timeout_s:.0f}s (travado)",
                    detail="\n".join(stderr_tail),
                )
    finally:
        _kill_tree(proc)
        for t in readers:
            t.join(timeout=5)

    if proc.returncode != 0:
        # a primeira linha de erro costuma ser a causa; a ultima, so o efeito
        keys = ("No such", "Unrecognized", "not found", "Unknown", "Invalid", "Error")
        lines = [ln for ln in stderr_tail if ln.strip()]
        last = next((ln for ln in lines if any(k in ln for k in keys)), lines[-1] if lines else "")
        raise ProcessFailed(
            f"ffmpeg saiu com codigo {proc.returncode}" + (f": {last[:300]}" if last else ""),
            returncode=proc.returncode,
            detail="\n".join(stderr_tail),
        )
    if on_progress:
        on_progress(1.0)


@cache
def has_filter(name: str) -> bool:
    """O build instalado tem este filtro? (ex.: 'subtitles' exige libass)."""
    try:
        out = subprocess.run([find_binary("ffmpeg"), "-hide_banner", "-filters"], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return re.search(rf"^\s*\S+\s+{re.escape(name)}\s", out, re.M) is not None


def require_filter(name: str, why: str) -> None:
    if not has_filter(name):
        raise DependencyMissing(f"este FFmpeg nao tem o filtro '{name}' ({why}); instale um build completo, "
                                "ex.: gyan.dev no Windows ou ffmpeg com libass")


@cache
def ffmpeg_major_version() -> int:
    """Versao principal do ffmpeg (0 se nao der para ler, ex.: build de git)."""
    try:
        out = subprocess.run([find_binary("ffmpeg"), "-version"], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0
    m = re.search(r"ffmpeg version n?(\d+)\.", out)
    return int(m.group(1)) if m else 0


def filter_script_args(script: Path) -> list[str]:
    """Filtergraph lido de arquivo: `-/filter_complex` no ffmpeg 7+, que removeu o
    `-filter_complex_script`; o antigo continua no 4-6."""
    major = ffmpeg_major_version()
    if major == 0 or major >= 7:
        return ["-/filter_complex", str(script)]
    return ["-filter_complex_script", str(script)]


def run_to_file(output: Path, build_args: Callable[[Path], Sequence[str]], **kw) -> Path:
    """Gera ``output`` de forma atomica: escreve em .part e renomeia se valido."""
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.stem + ".part" + output.suffix)
    tmp.unlink(missing_ok=True)
    try:
        run_ffmpeg(build_args(tmp), **kw)
        if not tmp.exists() or tmp.stat().st_size == 0:
            raise ProcessFailed("ffmpeg terminou sem gerar arquivo", returncode=0)
        os.replace(tmp, output)
        return output
    finally:
        tmp.unlink(missing_ok=True)


def probe(path: Path, timeout_s: float = 60) -> MediaInfo:
    if not path.is_file():
        raise InvalidMedia(f"arquivo nao existe: {path}")
    cmd = [find_binary("ffprobe"), "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", str(path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s,
                             encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as exc:
        raise ProcessTimeout(f"ffprobe travou em {path.name}") from exc
    if res.returncode != 0:
        raise InvalidMedia(f"ffprobe nao conseguiu ler {path.name}", detail=res.stderr[-2000:])

    data = json.loads(res.stdout or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"
                  and not s.get("disposition", {}).get("attached_pic")), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        raise InvalidMedia(f"{path.name} sem duracao valida (arquivo corrompido ou incompleto?)")

    fps = None
    if video and video.get("avg_frame_rate", "0/0") != "0/0":
        num, _, den = video["avg_frame_rate"].partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else None

    return MediaInfo(
        path=path, duration=duration, has_audio=audio is not None, has_video=video is not None,
        width=video.get("width") if video else None,
        height=video.get("height") if video else None, fps=fps,
    )


def require_audio(info: MediaInfo) -> MediaInfo:
    if not info.has_audio:
        raise InvalidMedia(f"{info.path.name} nao tem faixa de audio")
    return info


ENCODER_ARGS: dict[Encoder, list[str]] = {
    Encoder.CPU: ["-c:v", "libx264", "-preset", "faster", "-crf", "{crf}"],
    Encoder.NVIDIA: ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "{crf}"],
    Encoder.AMD: ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp",
                  "-qp_i", "{crf}", "-qp_p", "{crf}"],
    Encoder.INTEL: ["-c:v", "h264_qsv", "-global_quality", "{crf}"],
}


@cache
def encoder_works(enc: Encoder) -> bool:
    """Testa o encoder de verdade (1 frame). Listar em -encoders nao garante driver."""
    if enc is Encoder.CPU:
        return True
    try:
        run_ffmpeg(["-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                    *[a.replace("{crf}", "23") for a in ENCODER_ARGS[enc]],
                    "-frames:v", "1", "-f", "null", "-"], timeout_s=20, stall_timeout_s=20)
        return True
    except Exception:  # noqa: BLE001 - qualquer falha = encoder indisponivel
        return False


def pick_encoder(preferred: Encoder) -> Encoder:
    order = [preferred] if preferred is not Encoder.AUTO else [
        Encoder.NVIDIA, Encoder.AMD, Encoder.INTEL]
    for enc in order:
        if encoder_works(enc):
            return enc
    log.info("nenhum encoder de GPU funcionou, usando CPU", extra={"preferred": preferred.value})
    return Encoder.CPU


def encoder_args(enc: Encoder, crf: int) -> list[str]:
    return [a.replace("{crf}", str(crf)) for a in ENCODER_ARGS[enc]] + ["-pix_fmt", "yuv420p"]


# Caminhos dentro de filtros (subtitles=, metadata=print:file=) exigem escape em dois
# niveis e quebram com "C:", apostrofo ou colchete. Em vez de escapar, as etapas rodam
# o ffmpeg com cwd= na pasta de trabalho e passam so um nome simples ("subs.ass").
