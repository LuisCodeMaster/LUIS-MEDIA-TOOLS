"""Diagnostico do ambiente (usado pelo `luismedia doctor` e pela aba Diagnostico do app)."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .adapters import ffmpeg as ff
from .adapters.ollama import OllamaClient
from .core.config import Encoder, Settings
from .core.errors import LuisMediaError


@dataclass
class Check:
    name: str
    ok: bool
    info: str
    essential: bool = False
    fix: str = ""  # o que fazer quando falha


def run_checks(settings: Settings) -> list[Check]:
    checks: list[Check] = []
    ffmpeg_ok = True
    for b in ("ffmpeg", "ffprobe"):
        try:
            checks.append(Check(b, True, ff.find_binary(b), essential=True))
        except LuisMediaError as e:
            ffmpeg_ok = False
            checks.append(Check(b, False, str(e), essential=True,
                                fix="Instale o FFmpeg (winget install Gyan.FFmpeg) e reabra o programa."))
    if ffmpeg_ok:
        checks.append(Check("Legenda queimada (libass)", ff.has_filter("subtitles"), "filtro subtitles",
                            fix="Use um FFmpeg completo (gyan.dev no Windows)."))
        names = {Encoder.NVIDIA: "GPU NVIDIA (NVENC)", Encoder.AMD: "GPU AMD (AMF)", Encoder.INTEL: "GPU Intel (QSV)"}
        for enc, label in names.items():
            checks.append(Check(label, ff.encoder_works(enc), "teste real de 1 quadro",
                                fix="Opcional: sem GPU, o vídeo é codificado pela CPU."))
    try:
        import faster_whisper  # noqa: F401

        from .adapters.whisper import detect_device

        dev, comp = detect_device(settings.whisper.device)
        checks.append(Check("Whisper (transcrição)", True, f"modelo {settings.whisper.model}, {dev}/{comp}",
                            essential=True))
    except ImportError:
        checks.append(Check("Whisper (transcrição)", False, "faster-whisper não instalado", essential=True,
                            fix="Rode o Instalar.cmd de novo."))

    client = OllamaClient(settings.llm)
    up = client.is_running()
    checks.append(Check("Ollama (IA local)", up, settings.llm.base_url,
                        fix="Opcional: instale e abra o Ollama (ollama.com) para resumo, quiz, cortes e slides."))
    if up:
        try:
            has = client.has_model()
        except LuisMediaError:
            has = False
        checks.append(Check(f"Modelo {settings.llm.model}", has, "baixado" if has else "não baixado",
                            fix=f"Clique em 'Baixar modelo de IA' ou rode: ollama pull {settings.llm.model}"))
    try:
        from .adapters.pdf import find_browser

        checks.append(Check("Navegador (PDF da apostila)", True, find_browser()))
    except LuisMediaError as e:
        checks.append(Check("Navegador (PDF da apostila)", False, str(e), fix="Instale o Edge ou o Chrome."))
    return checks


def builtin_profiles() -> dict[str, Path]:
    """Perfis que vem com o programa: nome do arquivo (sem .yaml) -> caminho."""
    folder = resources.files("luismedia") / "profiles"
    return {Path(str(p)).stem: Path(str(p)) for p in folder.iterdir() if str(p).endswith(".yaml")}
