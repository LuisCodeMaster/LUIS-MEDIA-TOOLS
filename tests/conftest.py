"""Fixtures com midia SINTETICA gerada pelo proprio ffmpeg (lavfi).

Nada de video real no repositorio: os testes criam o que precisam em segundos, com
silencios e mudancas de cena em instantes conhecidos, entao da para conferir numeros.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

HAS_FFMPEG = shutil.which("ffmpeg") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg ausente")


def _has_libass() -> bool:
    if not HAS_FFMPEG:
        return False
    out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    return " subtitles " in out


needs_libass = pytest.mark.skipif(not _has_libass(), reason="ffmpeg sem libass (filtro subtitles)")


def _ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


@pytest.fixture(scope="session")
def lesson_video(tmp_path_factory) -> Path:
    """12 s de 'aula': fala 0-3, silencio curto 3-4.5, fala 4.5-7, pausa longa 7-11, fala 11-12.

    O video troca de cor em 4 s e 8 s (simula troca de slide).
    Pasta com espaco e apostrofo de proposito (quebrava o pipeline antigo).
    """
    d = tmp_path_factory.mktemp("aula d'Teste [1]")
    out = d / "aula 01.mp4"
    tone = "sine=frequency=440:sample_rate=48000"
    audio = (
        f"{tone}:duration=3[a0];anullsrc=r=48000:cl=mono,atrim=duration=1.5[s0];"
        f"{tone}:duration=2.5[a1];anullsrc=r=48000:cl=mono,atrim=duration=4[s1];"
        f"{tone}:duration=1[a2];[a0][s0][a1][s1][a2]concat=n=5:v=0:a=1[aout]"
    )
    video = (
        "color=c=red:s=320x240:r=25:d=4[c0];color=c=blue:s=320x240:r=25:d=4[c1];"
        "color=c=green:s=320x240:r=25:d=4[c2];[c0][c1][c2]concat=n=3:v=1:a=0[vout]"
    )
    _ff("-filter_complex", f"{audio};{video}", "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(out))
    return out


@pytest.fixture
def corrupt_video(tmp_path) -> Path:
    p = tmp_path / "quebrado.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"lixo" * 100)
    return p
