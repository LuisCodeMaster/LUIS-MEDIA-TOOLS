"""Etapas de IA: resumo executivo, quiz e selecao de cortes 9:16.

Toda resposta estruturada passa por schema pydantic (Quiz, ClipPlan) antes de ser usada.
Transcricoes longas sao resumidas em partes (map-reduce) em vez de cortadas no meio.
"""

from __future__ import annotations

import html
import random
from pathlib import Path

from ..adapters import ffmpeg as ff
from ..adapters.ollama import OllamaClient
from ..core.captions import clip_window, realign_words
from ..core.config import Encoder
from ..core.models import ClipPlan, ClipSuggestion, MediaInfo, Quiz, Segment, Transcript
from ..core.segmentation import SegmentationRules, segment_words
from ..core.style import SubtitleStyle, write_styled_ass

SYSTEM = ("Voce e um assistente pedagogico. Responda sempre em portugues do Brasil, "
          "com base APENAS no conteudo fornecido. Nao invente fatos.")


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Divide em partes de ate max_chars, quebrando em fim de frase quando possivel."""
    chunks, rest = [], text.strip()
    while len(rest) > max_chars:
        cut = max(rest.rfind(". ", 0, max_chars), rest.rfind("? ", 0, max_chars),
                  rest.rfind("! ", 0, max_chars))
        cut = cut + 1 if cut > max_chars // 2 else max_chars
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        chunks.append(rest)
    return chunks


def condensed_text(client: OllamaClient, tr: Transcript, max_chars: int) -> str:
    text = tr.plain_text()
    if len(text) <= max_chars:
        return text
    notes = [client.generate(f"Resuma em topicos objetivos o trecho de aula abaixo, sem perder "
                             f"conceitos, exemplos e definicoes:\n\n{part}", system=SYSTEM)
             for part in chunk_text(text, max_chars)]
    return "\n\n".join(notes)


def summary(client: OllamaClient, material: str, title: str) -> str:
    prompt = (f"Crie um Resumo Executivo em Markdown da aula \"{title}\" com as secoes:\n"
              "## Objetivo da aula\n## Pontos-chave\n## Conclusao pratica\n\n"
              f"Conteudo:\n{material}")
    return client.generate(prompt, system=SYSTEM).strip()


def quiz(client: OllamaClient, material: str, n: int = 5) -> Quiz:
    prompt = (f"Crie {n} perguntas objetivas de fixacao sobre o conteudo abaixo. Cada pergunta "
              "tem 1 resposta correta e exatamente 3 erradas plausiveis.\n\n"
              f"Conteudo:\n{material}")
    return client.generate_model(prompt, Quiz)


QUIZ_HTML = """<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quiz - {title}</title>
<style>
body{{background:#0f172a;color:#f8fafc;font-family:system-ui,'Segoe UI',sans-serif;max-width:800px;margin:0 auto;padding:40px 20px}}
h1{{text-align:center;color:#38bdf8}}.card{{background:#1e293b;padding:24px;border-radius:12px;margin-bottom:24px}}
.q{{font-size:1.15em;font-weight:600;margin-bottom:16px}}
button{{display:block;width:100%;text-align:left;background:#334155;color:#f8fafc;padding:14px 18px;margin-bottom:10px;border:1px solid #475569;border-radius:8px;font-size:1em;cursor:pointer}}
button.ok{{background:#166534;border-color:#22c55e}}button.no{{background:#991b1b;border-color:#ef4444}}
#placar{{text-align:center;font-size:1.2em;margin-top:24px}}
</style></head><body><h1>Quiz de fixação: {title}</h1>{cards}<div id="placar"></div>
<script>
let feitas=0,certas=0;const total={total};
document.querySelectorAll('.card').forEach(card=>card.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{{
 if(card.dataset.done)return;card.dataset.done=1;feitas++;
 const ok=b.dataset.c==='1';if(ok)certas++;b.classList.add(ok?'ok':'no');
 card.querySelector('[data-c="1"]').classList.add('ok');
 if(feitas===total)document.getElementById('placar').textContent=`Você acertou ${{certas}} de ${{total}}.`;
}})));
</script></body></html>"""


def quiz_html(q: Quiz, title: str, seed: str) -> str:
    rng = random.Random(seed)  # mesma ordem a cada geracao (reprodutivel)
    cards = []
    for i, item in enumerate(q.questions, 1):
        opts = [(item.correct, 1)] + [(w, 0) for w in item.wrong]
        rng.shuffle(opts)
        buttons = "".join(f'<button data-c="{c}">{"ABCD"[k]}) {html.escape(t)}</button>'
                          for k, (t, c) in enumerate(opts))
        cards.append(f'<div class="card"><div class="q">{i}. {html.escape(item.question)}</div>{buttons}</div>')
    return QUIZ_HTML.format(title=html.escape(title), cards="".join(cards), total=len(cards))


def pick_clips(client: OllamaClient, tr: Transcript, n: int, max_chars: int) -> list[ClipSuggestion]:
    lines, size = [], 0
    for s in tr.segments:
        line = f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}"
        if size + len(line) > max_chars:
            break
        lines.append(line)
        size += len(line)
    prompt = (f"Voce e editor de videos curtos. Escolha os {n} trechos mais impactantes e "
              "autocontidos (entre 20 e 60 segundos) da transcricao abaixo. Use os tempos em "
              "SEGUNDOS que aparecem entre colchetes. O titulo deve ser chamativo e curto.\n\n"
              + "\n".join(lines))
    plan = client.generate_model(prompt, ClipPlan)
    valid = [c for c in plan.clips if c.end <= tr.duration + 0.5]
    return sorted(valid, key=lambda c: c.start)[:n]


def render_vertical_clip(src: MediaInfo, clip: ClipSuggestion, captions: list[Segment], out: Path,
                         *, encoder: Encoder, crf: int, rules: SegmentationRules,
                         style: SubtitleStyle) -> Path:
    """Corte 9:16: fundo desfocado + video centralizado + legenda no estilo vertical
    (ex.: CapCut com palavra destacada), feita a partir das legendas ja revisadas."""
    from .media import subtitles_filter

    ff.require_filter("subtitles", "legenda nos cortes 9:16")
    work = out.parent
    dur = min(clip.end, src.duration) - clip.start
    local = clip_window(captions, clip.start, clip.start + dur)
    words = [w for c in local for w in (c.words or realign_words(c, c.text.replace("\n", " ")).words)]
    caps = segment_words(words, rules, shorts=True) if words else local
    if style.highlight != "none":  # o karaoke precisa das palavras dentro de cada legenda
        caps = [c.model_copy(update={"words": [w for w in words if c.start - 0.01 <= w.start < c.end]})
                for c in caps]
    ass_name = out.stem + ".ass"
    write_styled_ass(caps, work / ass_name, style, 1080, 1920)
    graph = ("[0:v]split=2[bg][fg];"
             "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:6[bgb];"
             "[fg]scale=1080:-2:force_original_aspect_ratio=decrease[fgs];"
             f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,{subtitles_filter(ass_name, work)}[v]")
    try:
        return ff.run_to_file(
            out,
            lambda tmp: ["-ss", f"{clip.start:.3f}", "-t", f"{dur:.3f}", "-i", str(src.path),
                         "-filter_complex", graph, "-map", "[v]", "-map", "0:a?",
                         *ff.encoder_args(encoder, crf), "-c:a", "aac", "-b:a", "192k",
                         "-movflags", "+faststart", str(tmp.resolve())],
            cwd=work, duration_hint=dur, timeout_s=max(300, dur * 10),
        )
    finally:
        (work / ass_name).unlink(missing_ok=True)
