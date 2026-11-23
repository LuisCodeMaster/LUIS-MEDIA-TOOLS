"""Configuracao tipada e validada (substitui $cfg, $global:* e caminhos fixos).

Ordem de precedencia: padrao do codigo < arquivo YAML/JSON do perfil < variaveis
de ambiente LUISMEDIA_* < argumentos da CLI.
"""

from __future__ import annotations

import json
import os
import sys
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .style import PRESETS_V, SubtitleStyle


def default_data_dir() -> Path:
    """Pasta de dados do usuario, por sistema operacional (nada de C:\\Users\\ferna)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "LuisMediaTools"


class Encoder(str, Enum):
    AUTO = "auto"
    CPU = "libx264"
    NVIDIA = "h264_nvenc"
    AMD = "h264_amf"
    INTEL = "h264_qsv"


class WhisperDevice(str, Enum):
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AutoCutConfig(_Strict):
    """Corte de silencio rapido ANTES da transcricao (modo antigo; o app usa o CleanupConfig)."""

    enabled: bool = False
    noise_db: float = Field(-32.0, le=0, ge=-80)
    min_silence_s: float = Field(1.1, gt=0)
    keep_pauses_longer_than_s: float = Field(2.5, gt=0)
    margin_s: float = Field(0.25, ge=0, le=1)
    export_edl: bool = True


class CleanupConfig(_Strict):
    """Limpeza da fala DEPOIS da transcricao: pausas e vicios, revisaveis na linha do tempo."""

    enabled: bool = True
    pauses: bool = True
    min_pause_s: float = Field(0.8, ge=0.3, le=5)
    keep_pause_s: float = Field(0.3, ge=0, le=1.5)
    max_pause_s: float = Field(6.0, ge=1, le=60)  # maiores sao mantidas (demonstracao)
    fillers: bool = True                          # "é...", "ãh", "hum" (e sugere "né", "tipo")
    trim_ends: bool = True
    export_edl: bool = True                       # timeline para DaVinci/Premiere

    def detection(self):
        from .cleanup import CleanupSettings

        return CleanupSettings(pauses=self.pauses, min_pause_s=self.min_pause_s, keep_pause_s=self.keep_pause_s,
                               max_pause_s=self.max_pause_s, fillers=self.fillers, trim_ends=self.trim_ends)


class AudioConfig(_Strict):
    master: bool = True
    target_lufs: float = Field(-14.0, ge=-30, le=-5)  # um unico valor para o produto todo
    true_peak_db: float = Field(-1.5, le=0)
    lra: float = Field(11.0, gt=0)


class WhisperConfig(_Strict):
    model: str = "medium"
    fallback_models: list[str] = ["small", "base"]
    device: WhisperDevice = WhisperDevice.AUTO
    compute_type: str = "auto"  # int8 na CPU, float16 na GPU
    language: str = "pt"
    beam_size: int = Field(5, ge=1, le=10)
    vad_filter: bool = True
    vocabulary: list[str] = []  # nomes, siglas e termos da aula (ajuda o Whisper a acertar)


class LLMConfig(_Strict):
    enabled: bool = True
    base_url: str = "http://127.0.0.1:11434"
    model: str = "llama3.2:3b"
    timeout_s: float = Field(180, gt=0)
    max_context_chars: int = Field(12_000, gt=1000)
    summary: bool = True
    quiz: bool = True
    clips: bool = False
    clips_count: int = Field(3, ge=1, le=10)


class RenderConfig(_Strict):
    encoder: Encoder = Encoder.AUTO
    hardsub: bool = True
    crf: int = Field(20, ge=0, le=51)


class SubtitleConfig(_Strict):
    max_chars_line: int = Field(42, ge=20, le=80)
    max_chars_shorts: int = Field(32, ge=16, le=60)
    min_duration_s: float = Field(0.8, gt=0)
    max_duration_s: float = Field(5.0, gt=0)
    max_cps: float = Field(17.0, ge=8, le=30)          # velocidade de leitura
    min_gap_s: float = Field(0.083, ge=0, le=0.5)      # 2 quadros entre legendas
    shorts_version: bool = True
    review: bool = False                               # parar para revisar antes de queimar
    replacements: dict[str, str] = {}                  # correcoes automaticas: "Wisper" -> "Whisper"
    style_h: SubtitleStyle = SubtitleStyle()           # legenda queimada (16:9)
    style_v: SubtitleStyle = PRESETS_V["CapCut amarelo"].model_copy()  # cortes 9:16


class SlidesConfig(_Strict):
    enabled: bool = True
    scene_threshold: float = Field(0.25, gt=0, lt=1)
    handout: bool = True       # apostila ilustrada em HTML
    handout_pdf: bool = True   # + PDF via navegador headless (Edge/Chrome/Chromium)


class OutputConfig(_Strict):
    chapters: bool = True      # capitulos-youtube.txt somando os videos do lote
    zip_package: bool = True   # Entregavel.zip (sem os videos, que ja estao na pasta)
    zip_include_videos: bool = False


class Settings(_Strict):
    profile_name: str = "curso-completo"
    data_dir: Path = Field(default_factory=default_data_dir)
    max_parallel_jobs: int = Field(1, ge=1, le=8)
    ffmpeg_threads: int = Field(0, ge=0)  # 0 = ffmpeg decide
    keep_intermediates: bool = False
    move_source_files: bool = False  # o script antigo MOVIA os originais; agora e opt-in
    autocut: AutoCutConfig = AutoCutConfig()
    cleanup: CleanupConfig = CleanupConfig()
    audio: AudioConfig = AudioConfig()
    whisper: WhisperConfig = WhisperConfig()
    llm: LLMConfig = LLMConfig()
    render: RenderConfig = RenderConfig()
    subtitles: SubtitleConfig = SubtitleConfig()
    slides: SlidesConfig = SlidesConfig()
    output: OutputConfig = OutputConfig()

    @field_validator("data_dir")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return Path(os.path.expandvars(str(v))).expanduser()

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        data: dict = {}
        if path is not None:
            text = path.read_text(encoding="utf-8-sig")  # tolera BOM do PowerShell
            if path.suffix.lower() in {".yaml", ".yml"}:
                import yaml

                data = yaml.safe_load(text) or {}
            else:
                data = json.loads(text)
        # Override simples por env: LUISMEDIA_LLM__MODEL=qwen2.5:3b
        for key, value in os.environ.items():
            if key.startswith("LUISMEDIA_"):
                parts = key[len("LUISMEDIA_"):].lower().split("__")
                node = data
                for p in parts[:-1]:
                    node = node.setdefault(p, {})
                node[parts[-1]] = value
        return cls.model_validate(data)
