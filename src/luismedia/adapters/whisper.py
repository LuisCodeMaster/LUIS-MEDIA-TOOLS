"""Adapter de transcricao com faster-whisper.

Antes: codigo Python montado como string dentro do PowerShell (quebrava com apostrofo
no caminho), modelo 'medium' recarregado a cada video, sempre CPU, e qualquer erro
virava um print enquanto o pipeline seguia como se tivesse dado certo.

Agora: modelo carregado uma vez e reutilizado; deteccao de GPU; degradacao automatica
(CUDA sem memoria -> CPU int8 -> modelo menor); erro tipado.
"""

from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from ..core.config import WhisperConfig, WhisperDevice
from ..core.errors import Cancelled, DependencyMissing, OutOfMemory, TranscriptionFailed
from ..core.logging import get_logger
from ..core.models import Segment, Transcript, Word

log = get_logger("whisper")
ProgressFn = Callable[[float], None]


def detect_device(pref: WhisperDevice) -> tuple[str, str]:
    """Retorna (device, compute_type). CTranslate2 suporta CUDA; ROCm/DirectML nao."""
    if pref is WhisperDevice.CPU:
        return "cpu", "int8"
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # noqa: BLE001
        pass
    if pref is WhisperDevice.CUDA:
        log.warning("CUDA pedida mas indisponivel; usando CPU")
    return "cpu", "int8"


def load_audio(path: Path):
    """Le o WAV mono 16 kHz que o pipeline ja gera e entrega ao Whisper como numpy.

    Evita o decodificador do faster-whisper (PyAV): no PyAV 14+ a opcao `metadata_errors`
    que ele usa foi removida e a transcricao falhava com
    "open() got an unexpected keyword argument 'metadata_errors'".
    Qualquer outro formato e convertido antes pelo FFmpeg.
    """
    import subprocess
    import wave

    import numpy as np

    from . import ffmpeg as ff

    try:
        with wave.open(str(path), "rb") as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000):
                raw = w.readframes(w.getnframes())
                return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except (wave.Error, EOFError, OSError):
        pass
    res = subprocess.run([ff.find_binary("ffmpeg"), "-nostdin", "-v", "error", "-i", str(path),
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, timeout=3600, **ff.NO_WINDOW)
    if res.returncode != 0:
        raise TranscriptionFailed("nao consegui ler o audio para transcrever",
                                  detail=res.stderr.decode("utf-8", "replace")[-1500:])
    return np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def vocabulary_kwargs(cfg: WhisperConfig) -> dict:
    """Termos da aula (nomes, siglas, formulas): vao como contexto inicial e como hotwords,
    o que faz o Whisper preferir essa grafia ("Vygotsky", "LGPD", "Bhaskara")."""
    terms = [t.strip() for t in cfg.vocabulary if t.strip()]
    if not terms:
        return {}
    joined = ", ".join(dict.fromkeys(terms))[:600]
    return {"initial_prompt": f"Aula com os termos: {joined}.", "hotwords": joined}


def _is_oom(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in ("out of memory", "cuda_error_out_of_memory",
                                  "cublas_status_alloc_failed", "bad_alloc"))


class WhisperEngine:
    """Singleton por processo: carregar o 'medium' custa segundos e ~1.5 GB."""

    _lock = Lock()

    def __init__(self, cfg: WhisperConfig) -> None:
        self.cfg = cfg
        self._model = None
        self._loaded: tuple[str, str, str] | None = None
        self.cancel = None  # threading.Event opcional, checado a cada segmento

    def _load(self, model: str, device: str, compute: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise DependencyMissing("faster-whisper nao instalado (pip install luismedia[whisper])") from exc
        key = (model, device, compute)
        if self._loaded != key:
            self._model = None
            gc.collect()
            log.info("carregando modelo", extra={"model": model, "device": device, "compute": compute})
            self._model = WhisperModel(model, device=device, compute_type=compute)
            self._loaded = key
        return self._model

    def _attempts(self) -> list[tuple[str, str, str]]:
        device, compute = detect_device(self.cfg.device)
        if self.cfg.compute_type != "auto":
            compute = self.cfg.compute_type
        plan = [(self.cfg.model, device, compute)]
        if device == "cuda":
            plan.append((self.cfg.model, "cuda", "int8_float16"))  # metade da VRAM
            plan.append((self.cfg.model, "cpu", "int8"))
        plan += [(m, "cpu", "int8") for m in self.cfg.fallback_models]
        return list(dict.fromkeys(plan))

    def transcribe(self, audio: Path, duration: float, on_progress: ProgressFn | None = None) -> Transcript:
        with self._lock:  # um modelo, uma transcricao por vez (evita estourar RAM/VRAM)
            last: BaseException | None = None
            for model_name, device, compute in self._attempts():
                try:
                    model = self._load(model_name, device, compute)
                    seg_iter, info = model.transcribe(
                        load_audio(audio), language=self.cfg.language, beam_size=self.cfg.beam_size,
                        word_timestamps=True, vad_filter=self.cfg.vad_filter, **vocabulary_kwargs(self.cfg),
                    )
                    segments: list[Segment] = []
                    for s in seg_iter:  # gerador: o trabalho acontece aqui
                        if self.cancel is not None and self.cancel.is_set():
                            raise Cancelled("transcricao cancelada")
                        words = [Word(start=w.start, end=max(w.end, w.start), text=w.word,
                                      probability=w.probability) for w in (s.words or [])]
                        segments.append(Segment(start=s.start, end=max(s.end, s.start),
                                                text=s.text, words=words))
                        if on_progress and duration:
                            on_progress(min(1.0, s.end / duration))
                    return Transcript(language=info.language, duration=duration,
                                      segments=segments, model=model_name, device=device)
                except (DependencyMissing, Cancelled):
                    raise
                except Exception as exc:  # noqa: BLE001
                    last = exc
                    if not _is_oom(exc) and device == "cpu":
                        # ex.: download do modelo bloqueado (403/sem internet), audio ilegivel
                        raise TranscriptionFailed(
                            f"transcricao falhou com o modelo {model_name}: {exc}",
                            detail=repr(exc)) from exc
                    log.warning("degradando transcricao", extra={
                        "model": model_name, "device": device, "error": str(exc)[:300]})
                    self._model, self._loaded = None, None
                    gc.collect()
            raise OutOfMemory("memoria insuficiente ate no menor modelo") from last
