"""Adapter do Ollama com health-check, timeout, retry e saida JSON validada.

Antes: urllib sem timeout (podia travar para sempre), erro virava ``None`` em silencio
e o JSON do modelo era aceito sem validar (timecode "00:35" derrubava o gerador de cortes).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..core.config import LLMConfig
from ..core.errors import DependencyMissing, LLMOutputInvalid, ServiceUnavailable
from ..core.logging import get_logger
from ..core.retry import with_retry

log = get_logger("ollama")
M = TypeVar("M", bound=BaseModel)


class OllamaClient:
    def __init__(self, cfg: LLMConfig, opener: Callable = urllib.request.urlopen) -> None:
        self.cfg = cfg
        self._open = opener  # injetavel nos testes

    def _post(self, path: str, body: dict, timeout: float) -> dict:
        req = urllib.request.Request(
            self.cfg.base_url.rstrip("/") + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            if exc.code == 404 and "not found" in detail.lower():
                raise DependencyMissing(f"modelo {self.cfg.model} nao baixado", detail=detail) from exc
            if exc.code >= 500:
                # Ollama devolve 500 quando falta RAM/VRAM para carregar o modelo
                raise ServiceUnavailable(f"Ollama HTTP {exc.code}", detail=detail) from exc
            raise LLMOutputInvalid(f"Ollama HTTP {exc.code}", detail=detail) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ServiceUnavailable(f"Ollama inacessivel em {self.cfg.base_url}: {exc}") from exc

    def _get(self, path: str, timeout: float = 5) -> dict:
        try:
            with self._open(self.cfg.base_url.rstrip("/") + path, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise ServiceUnavailable(f"Ollama inacessivel: {exc}") from exc

    # ---- primeira execucao / zero-config ---------------------------------
    def is_running(self) -> bool:
        try:
            self._get("/api/version")
            return True
        except ServiceUnavailable:
            return False

    def has_model(self) -> bool:
        tags = self._get("/api/tags").get("models", [])
        wanted = self.cfg.model if ":" in self.cfg.model else self.cfg.model + ":latest"
        return any(m.get("name") == wanted for m in tags)

    def pull_model(self, on_progress: Callable[[float], None] | None = None) -> None:
        """Baixa o modelo com progresso (stream NDJSON da API /api/pull)."""
        req = urllib.request.Request(
            self.cfg.base_url.rstrip("/") + "/api/pull",
            data=json.dumps({"model": self.cfg.model, "stream": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self._open(req, timeout=3600) as resp:
            for raw in resp:
                evt = json.loads(raw or b"{}")
                if "error" in evt:
                    raise ServiceUnavailable(f"falha ao baixar modelo: {evt['error']}")
                if on_progress and evt.get("total"):
                    on_progress(evt.get("completed", 0) / evt["total"])

    # ---- geracao ----------------------------------------------------------
    def generate(self, prompt: str, *, json_mode: bool = False, system: str | None = None) -> str:
        body: dict = {"model": self.cfg.model, "prompt": prompt, "stream": False,
                      "options": {"temperature": 0.3}}
        if system:
            body["system"] = system
        if json_mode:
            body["format"] = "json"

        def _call() -> str:
            out = self._post("/api/generate", body, timeout=self.cfg.timeout_s)
            text = out.get("response", "")
            if not text.strip():
                raise LLMOutputInvalid("resposta vazia do modelo")
            return text

        return with_retry(_call, attempts=3, op_name="ollama.generate")

    def generate_model(self, prompt: str, schema: type[M], *, attempts: int = 3) -> M:
        """Pede JSON e valida com pydantic; se vier invalido, pede de novo com o erro."""
        hint = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        current = f"{prompt}\n\nResponda APENAS com JSON valido neste schema:\n{hint}"
        last_err = ""
        for attempt in range(1, attempts + 1):
            raw = self.generate(current, json_mode=True)
            try:
                return schema.model_validate_json(raw)
            except ValidationError as exc:
                last_err = str(exc)[:800]
                log.warning("JSON do LLM invalido", extra={"attempt": attempt, "error": last_err})
                current = (f"{prompt}\n\nSua resposta anterior era invalida: {last_err}\n"
                           f"Corrija e responda APENAS com JSON neste schema:\n{hint}")
        raise LLMOutputInvalid("modelo nao produziu JSON valido", detail=last_err)
