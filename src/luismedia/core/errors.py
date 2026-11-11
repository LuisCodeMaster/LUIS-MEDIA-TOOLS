"""Hierarquia de erros do dominio.

Cada erro diz se vale a pena tentar de novo (``retryable``). O runner usa isso
para decidir entre retry, fallback (GPU -> CPU) ou falha da etapa.
"""

from __future__ import annotations


class LuisMediaError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class DependencyMissing(LuisMediaError):
    """FFmpeg, modelo do Whisper ou Ollama ausente na maquina."""


class InvalidMedia(LuisMediaError):
    """Arquivo corrompido, sem audio, duracao zero etc."""


class ProcessTimeout(LuisMediaError):
    retryable = True


class ProcessFailed(LuisMediaError):
    """Processo externo terminou com codigo != 0."""

    def __init__(self, message: str, *, returncode: int, detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.returncode = returncode


class ServiceUnavailable(LuisMediaError):
    """Ollama fora do ar, conexao recusada, HTTP 5xx."""

    retryable = True


class OutOfMemory(LuisMediaError):
    """CUDA/RAM insuficiente. Nao repete igual: o chamador deve degradar."""


class LLMOutputInvalid(LuisMediaError):
    """Resposta do LLM nao bate com o schema esperado."""

    retryable = True
