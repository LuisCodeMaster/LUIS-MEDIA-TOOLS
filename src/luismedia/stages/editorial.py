"""Apostila ilustrada: cada slide detectado + o que foi dito enquanto ele estava na tela.

Corrige o motor antigo, que procurava pastas que o pipeline nao criava (apostila vazia)
e montava HTML sem escapar o texto falado.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

from ..core.models import SlideFrame, Transcript

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f8fafc;color:#1e293b;font-family:system-ui,'Segoe UI',Roboto,Arial,sans-serif;line-height:1.7;padding:40px 20px}
.doc{max-width:900px;margin:0 auto;background:#fff;padding:56px 72px;border-radius:12px;border:1px solid #e2e8f0}
header{border-bottom:2px solid #0f172a;padding-bottom:24px;margin-bottom:36px}
h1{font-size:2.2rem;color:#0f172a;font-weight:800}.sub{color:#64748b;text-transform:uppercase;letter-spacing:1px;font-weight:600}
h2{font-size:1.4rem;margin:28px 0 12px;color:#0f172a}h3{font-size:1.15rem;margin:20px 0 8px}
.resumo{background:#f1f5f9;border-radius:10px;padding:24px 28px;margin-bottom:40px}.resumo ul{margin:8px 0 8px 22px}
.bloco{margin-bottom:44px;page-break-inside:avoid}
.tempo{display:inline-block;background:#eff6ff;color:#2563eb;border:1px solid #bfdbfe;font-size:.85rem;font-weight:700;padding:2px 10px;border-radius:6px;margin-bottom:10px}
.slide img{width:100%;display:block;border-radius:8px;border:1px solid #cbd5e1;margin:8px 0 16px}
.texto p{font-size:1.08rem;color:#334155;text-align:justify}
footer{margin-top:56px;border-top:1px solid #e2e8f0;padding-top:16px;font-size:.85rem;color:#94a3b8}
@media print{body{background:#fff;padding:0}.doc{border:none;padding:0;max-width:100%}}
"""


def _ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:d}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def markdown_to_html(md: str) -> str:
    """Markdown basico (titulos, listas, negrito) com o texto sempre escapado."""
    out, in_list = [], False
    for raw in md.splitlines():
        line = html.escape(raw.strip())
        line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
        if line.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{line[2:]}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if m := re.match(r"(#{1,3})\s+(.*)", line):
            level = min(3, len(m.group(1)) + 1)
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
        elif line:
            out.append(f"<p>{line}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def build_handout(title: str, slides: list[SlideFrame], tr: Transcript, html_path: Path,
                  summary_md: str | None = None) -> Path:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = []
    if slides:
        for i, sl in enumerate(slides):
            t_end = slides[i + 1].timestamp if i + 1 < len(slides) else float("inf")
            said = " ".join(s.text.strip() for s in tr.segments if sl.timestamp <= s.start < t_end)
            rel = Path(os.path.relpath(sl.path, html_path.parent)).as_posix()
            text = html.escape(said) if said else "<em>Explicacao visual demonstrada na tela.</em>"
            blocks.append(f'<section class="bloco"><div class="tempo">{_ts(sl.timestamp)}</div>'
                          f'<div class="slide"><img src="{html.escape(rel)}" alt="Slide {i + 1}"></div>'
                          f'<div class="texto"><p>{text}</p></div></section>')
    else:
        blocks.append(f'<section class="bloco"><div class="texto"><p>{html.escape(tr.plain_text())}</p></div></section>')

    resumo = f'<div class="resumo">{markdown_to_html(summary_md)}</div>' if summary_md else ""
    doc = (f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
           f'<meta name="viewport" content="width=device-width, initial-scale=1">'
           f'<title>Apostila - {html.escape(title)}</title><style>{CSS}</style></head><body>'
           f'<div class="doc"><header><div class="sub">Material didatico</div><h1>{html.escape(title)}</h1>'
           f'</header>{resumo}{"".join(blocks)}<footer>Gerado pelo LUIS MEDIA TOOLS</footer></div></body></html>')
    html_path.write_text(doc, encoding="utf-8")
    return html_path
