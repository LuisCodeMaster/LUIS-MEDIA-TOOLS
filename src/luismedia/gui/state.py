"""Preferencias do app: configuracao base (aba Configuracoes) + estado da tela (ultimo preset,
pasta de saida). Guardadas em JSON na pasta de dados do usuario."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..core.config import Settings, default_data_dir

PRESETS = {  # rotulo na tela -> arquivo em luismedia/profiles
    "Curso completo": "curso-completo",
    "Foco em redes sociais": "redes-sociais",
    "Pré-edição (DaVinci / Premiere)": "pre-edicao-nle",
}
PRESET_HINTS = {
    "Curso completo": "Tudo ativado: vídeo sem pausas, legendas, voz masterizada, apostila, quiz e cortes.",
    "Foco em redes sociais": "Vídeo enxuto com legenda queimada e 5 cortes 9:16. Sem apostila.",
    "Pré-edição (DaVinci / Premiere)": "Autocut + timeline EDL + legendas para terminar no editor. Sem IA.",
    "Personalizado": "Suas escolhas abaixo.",
}
CUSTOM = "Personalizado"


def data_dir() -> Path:
    d = default_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read(name: str) -> dict[str, Any]:
    p = data_dir() / name
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(name: str, data: dict[str, Any]) -> None:
    p = data_dir() / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def load_base_settings() -> Settings:
    """Configuracao salva na aba Configuracoes; se estiver invalida, volta ao padrao."""
    try:
        return Settings.model_validate(_read("config.json"))
    except Exception:  # noqa: BLE001
        return Settings()


def save_base_settings(settings: Settings) -> None:
    _write("config.json", settings.model_dump(mode="json", exclude={"data_dir"}))


def load_ui() -> dict[str, Any]:
    return _read("ui.json")


def save_ui(data: dict[str, Any]) -> None:
    _write("ui.json", data)


def deep_merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def compose(base: Settings, options: dict[str, Any]) -> Settings:
    """Configuracao base + escolhas da tela Processar (validadas de novo pelo pydantic)."""
    return Settings.model_validate(deep_merge(base.model_dump(mode="json"), options))
