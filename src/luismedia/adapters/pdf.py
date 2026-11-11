"""HTML -> PDF com o navegador Chromium ja instalado (Edge no Windows, Chrome/Chromium).

Sem dependencia nova: o Edge vem em todo Windows 10/11. Caminho customizado via
LUISMEDIA_BROWSER.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ..core.errors import DependencyMissing, ProcessFailed, ProcessTimeout
from .ffmpeg import NO_WINDOW


def find_browser() -> str:
    env = os.environ.get("LUISMEDIA_BROWSER")
    if env and Path(env).is_file():
        return env
    candidates: list[str] = []
    if sys.platform == "win32":
        for base in filter(None, (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"),
                                  os.environ.get("LOCALAPPDATA"))):
            candidates += [rf"{base}\Microsoft\Edge\Application\msedge.exe",
                           rf"{base}\Google\Chrome\Application\chrome.exe"]
    elif sys.platform == "darwin":
        candidates += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                       "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                       "/Applications/Chromium.app/Contents/MacOS/Chromium"]
    for c in candidates:
        if Path(c).is_file():
            return c
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    raise DependencyMissing("nenhum navegador Chromium encontrado para gerar PDF (Edge, Chrome ou Chromium)")


def html_to_pdf(html_file: Path, pdf_file: Path, timeout_s: float = 180) -> Path:
    browser = find_browser()
    pdf_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = pdf_file.with_suffix(".part.pdf")
    tmp.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="lmt_browser_") as profile:
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-first-run",
               f"--user-data-dir={profile}", "--no-pdf-header-footer",
               f"--print-to-pdf={tmp}", html_file.resolve().as_uri()]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, **NO_WINDOW,
                                 encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as exc:
            tmp.unlink(missing_ok=True)
            raise ProcessTimeout("navegador travou gerando o PDF") from exc
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise ProcessFailed("navegador nao gerou o PDF", returncode=res.returncode,
                            detail=(res.stderr or "")[-1500:])
    os.replace(tmp, pdf_file)
    return pdf_file
