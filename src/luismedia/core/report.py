"""Relatorio do professor: um retrato da aula para gravar melhor a proxima.

Tudo sai das palavras com tempo do Whisper e dos cortes (pausas, vicios, regravacoes):
ritmo (palavras por minuto ao longo da aula), vicios por tipo, palavras-muleta, regravacoes,
perguntas para a turma, legendas rapidas demais e o tempo economizado na edicao. As notas
sao indicadores automaticos, nao uma avaliacao definitiva, e o HTML diz isso.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from collections.abc import Sequence

from .cleanup import Cut, _bare, _squeeze, active_spans, all_words, filler_kind
from .models import Segment
from .segmentation import cps

CRUTCH_WORDS = {"basicamente", "literalmente", "exatamente", "obviamente", "enfim", "beleza", "entendeu",
                "sabe", "tipo", "assim", "certo", "ok", "entao", "ne", "ta", "realmente", "praticamente",
                "simplesmente", "justamente", "inclusive", "galera", "pessoal"}
STOPWORDS = {"que", "para", "como", "mais", "isso", "essa", "esse", "esta", "este", "voce", "voces", "porque",
             "quando", "aqui", "entao", "tambem", "muito", "sobre", "ainda", "depois", "fazer", "onde", "aquele",
             "aquela", "pode", "vamos", "temos", "estao", "nossa", "nosso", "seus", "suas", "pela", "pelo",
             "entre", "cada", "outro", "outra", "mesmo", "mesma", "agora", "sempre", "nunca", "tudo", "todos",
             "todas", "algum", "alguma", "quero", "gente"}
IDEAL_WPM = (130, 170)
WINDOW_S = 30.0
KIND_NAMES = {"pausa": "Pausas", "inicio": "Silêncio no começo", "fim": "Silêncio no fim", "vicio": "Vícios",
              "repeticao": "Regravações", "manual": "Cortes manuais", "texto": "Apagado no texto"}


def _mmss(t: float) -> str:
    t = max(0, int(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def _runs(words, gap: float = 1.0) -> list[tuple[float, float, int]]:
    """Trechos de fala continua: (inicio, fim, palavras)."""
    out: list[tuple[float, float, int]] = []
    for w in words:
        if out and w.start - out[-1][1] < gap:
            a, _, n = out[-1]
            out[-1] = (a, w.end, n + 1)
        else:
            out.append((w.start, w.end, 1))
    return out


def _score(value: float, good: tuple[float, float], bad: tuple[float, float]) -> int:
    """100 dentro da faixa boa, caindo linearmente ate 30 na faixa ruim."""
    lo, hi = good
    if lo <= value <= hi:
        return 100
    edge, far = (lo, bad[0]) if value < lo else (hi, bad[1])
    frac = min(1.0, abs(value - edge) / max(1e-6, abs(far - edge)))
    return round(100 - 70 * frac)


def build_report(captions: Sequence[Segment], cuts: Sequence[Cut], duration: float,
                 max_cps: float = 17.0) -> dict:
    words = all_words(captions)
    runs = _runs(words)
    speech = sum(b - a for a, b, _ in runs) or 1e-6
    wpm = len(words) / speech * 60 if words else 0.0

    # ritmo ao longo da aula
    timeline, fast, slow = [], [], []
    t = 0.0
    while t < max(duration, words[-1].end if words else 0):
        ws = [w for w in words if t <= w.start < t + WINDOW_S]
        sp = sum(max(0.0, min(b, t + WINDOW_S) - max(a, t)) for a, b, _ in runs)
        rate = len(ws) / sp * 60 if sp >= 8 else None
        timeline.append({"t": t, "wpm": round(rate) if rate else None})
        if rate and rate > 190:
            fast.append({"t": t, "wpm": round(rate)})
        elif rate and rate < 100:
            slow.append({"t": t, "wpm": round(rate)})
        t += WINDOW_S

    # vicios e muletas
    # mostra a palavra como foi falada ("né", "função"), nao a forma sem acento usada na contagem
    forms: dict[str, Counter[str]] = {}
    for w in words:
        forms.setdefault(_bare(w.text), Counter())[w.text.strip(" ,.;:!?…\"'").lower()] += 1

    def show(key: str) -> str:
        c = forms.get(key)
        return c.most_common(1)[0][0] if c else key

    fillers: Counter[str] = Counter()
    for i, w in enumerate(words):
        if filler_kind(words, i):
            key = _squeeze(_bare(w.text))
            label = "é…" if key in ("e", "ee", "eh") else "ã…" if key in ("a", "aa") else show(key)
            fillers[label or w.text.strip()] += 1
    toks = [_bare(w.text) for w in words]
    counted = {_bare(k) for k in fillers}
    crutches = Counter(show(t) for t in toks if t in CRUTCH_WORDS and t not in counted)
    content = Counter(show(t) for t in toks if len(t) >= 5 and t not in STOPWORDS and t not in CRUTCH_WORDS)
    minutes = max(duration, 1) / 60

    # cortes por tipo (uniao, sem contar sobreposicao duas vezes)
    removed = {}
    for kind in KIND_NAMES:
        secs = sum(s.end - s.start for s in active_spans([c for c in cuts if c.kind == kind]))
        if secs:
            removed[kind] = round(secs, 1)
    total_removed = sum(s.end - s.start for s in active_spans(cuts))
    retakes = []
    for c in cuts:
        if c.kind == "repeticao":
            m = re.search(r"“(.*)”", c.label)
            retakes.append({"t": c.start, "text": m.group(1) if m else c.label, "enabled": c.enabled})

    longest = max(((b - a, a) for a, b, _ in _runs(words, 0.6)), default=(0.0, 0.0))
    long_pauses = [(b.start - a.end, a.end) for a, b in zip(words, words[1:], strict=False) if b.start - a.end >= 6]
    questions = sum(1 for c in captions if "?" in c.text)
    fast_caps = sum(1 for c in captions if cps(c) > max_cps + 0.5)

    filler_rate = sum(fillers.values()) / minutes
    q_rate = questions / minutes * 10
    scores = {
        "ritmo": _score(wpm, IDEAL_WPM, (80, 230)),
        "fluencia": _score(filler_rate, (0, 1.0), (0, 6.0)),
        "clareza": _score(len(retakes) / minutes * 10 + (fast_caps / max(1, len(captions))) * 20, (0, 1.5), (0, 8)),
        "engajamento": _score(q_rate, (3, 1e9), (0, 1e9)),
    }
    scores["geral"] = round(sum(scores.values()) / len(scores))
    return {
        "duration": duration, "final_duration": max(0.0, duration - total_removed),
        "removed_total": round(total_removed, 1), "removed": removed,
        "words": len(words), "speech_s": round(speech, 1), "wpm": round(wpm),
        "timeline": timeline, "fast": fast, "slow": slow,
        "fillers": dict(fillers.most_common()), "fillers_per_min": round(filler_rate, 2),
        "crutches": {k: v for k, v in crutches.most_common() if v >= max(5, round(minutes))},
        "top_words": content.most_common(8),
        "retakes": retakes, "questions": questions, "questions_per_10min": round(q_rate, 1),
        "longest_run": {"s": round(longest[0], 1), "t": longest[1]},
        "long_pauses": [{"s": round(d, 1), "t": t} for d, t in long_pauses],
        "fast_captions": fast_caps, "captions": len(captions), "scores": scores, "tips": [],
    }


def summary_line(r: dict) -> str:
    parts = [f"{r['wpm']} palavras/min"]
    if r["fillers"]:
        parts.append(f"{sum(r['fillers'].values())} vícios")
    if r["retakes"]:
        parts.append(f"{len(r['retakes'])} regravações")
    parts.append(f"nota {r['scores']['geral']}")
    return " · ".join(parts)


def auto_tips(r: dict) -> list[str]:
    """Dicas sem IA, a partir dos numeros."""
    tips = []
    lo, hi = IDEAL_WPM
    if r["wpm"] > hi:
        tips.append(f"Você falou em média {r['wpm']} palavras por minuto; para aula, {lo}–{hi} costuma render "
                    "melhor. Pausas curtas depois de cada conceito ajudam a turma a acompanhar.")
    elif r["wpm"] and r["wpm"] < lo:
        tips.append(f"Ritmo de {r['wpm']} palavras por minuto: dá para acelerar um pouco nas partes de revisão "
                    "e guardar a calma para os conceitos novos.")
    if r["fillers_per_min"] > 2:
        top = ", ".join(f"“{k}” ({v}×)" for k, v in list(r["fillers"].items())[:3])
        tips.append(f"Os vícios mais frequentes foram {top}. Trocar o “é…” por um segundo de silêncio "
                    "soa mais seguro e a edição corta igual.")
    for word, n in list(r["crutches"].items())[:2]:
        tips.append(f"A palavra “{word}” apareceu {n} vezes. Vale variar ou simplesmente tirar.")
    if len(r["retakes"]) >= 3:
        tips.append(f"Foram {len(r['retakes'])} frases recomeçadas. Ter um roteiro com os tópicos à vista "
                    "reduz as regravações.")
    if r["questions_per_10min"] < 1.5:
        tips.append("Quase não houve perguntas para a turma. Uma pergunta a cada poucos minutos "
                    "(“o que vocês acham que acontece se…?”) prende mais a atenção.")
    if r["longest_run"]["s"] > 90:
        tips.append(f"O maior trecho sem pausa teve {r['longest_run']['s']:.0f} s (em {_mmss(r['longest_run']['t'])}). "
                    "Dividir em blocos menores facilita a compreensão e os cortes para redes.")
    return tips or ["Aula bem equilibrada: ritmo, fluência e engajamento dentro do esperado. Continue assim!"]


# ------------------------------------------------------------------ HTML
def _bar(label: str, value: int) -> str:
    color = "#22c55e" if value >= 80 else "#f59e0b" if value >= 55 else "#ef4444"
    return (f'<div class="score"><div class="sl">{label}</div><div class="track"><div class="fill" '
            f'style="width:{value}%;background:{color}"></div></div><div class="sv">{value}</div></div>')


def _chart(timeline: list[dict]) -> str:
    pts = [(p["t"], p["wpm"]) for p in timeline if p["wpm"]]
    if len(pts) < 2:
        return ""
    w, h = 640, 170
    top = max(200, max(v for _, v in pts) + 20)
    base = max(0, min(60, min(v for _, v in pts) - 20))
    tmax = timeline[-1]["t"] + WINDOW_S
    def x(t: float) -> float:
        return 30 + (w - 40) * t / tmax
    def y(v: float) -> float:
        return h - 20 - (h - 35) * (min(v, top) - base) / (top - base)
    lo, hi = IDEAL_WPM
    path = " ".join(f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(v):.1f}" for i, (t, v) in enumerate(pts))
    ticks = "".join(f'<text x="{x(t):.0f}" y="{h - 4}" class="tk" text-anchor="{a}">{_mmss(t)}</text>'
                    for t, a in zip([tmax * k / 4 for k in range(5)],
                                    ["start", "middle", "middle", "middle", "end"], strict=True))
    return (f'<svg viewBox="0 0 {w} {h}" class="chart">'
            f'<rect x="30" y="{y(hi):.1f}" width="{w - 40}" height="{y(lo) - y(hi):.1f}" class="band"/>'
            f'<text x="2" y="{y(hi) + 4:.0f}" class="tk">{hi}</text><text x="2" y="{y(lo) + 4:.0f}" class="tk">{lo}</text>'
            f'<path d="{path}" class="line"/>{ticks}</svg>')


def render_html(r: dict, title: str) -> str:
    e = html.escape
    s = r["scores"]
    removed = "".join(f"<li>{e(KIND_NAMES.get(k, k))}: <b>{v:.0f} s</b></li>" for k, v in r["removed"].items())
    fillers = "".join(f"<li>“{e(k)}” <b>{v}×</b></li>" for k, v in list(r["fillers"].items())[:8]) or "<li>Nenhum</li>"
    crutches = "".join(f"<li>“{e(k)}” <b>{v}×</b></li>" for k, v in r["crutches"].items()) or "<li>Nenhuma em excesso</li>"
    retakes = "".join(f"<li><span class='t'>{_mmss(x['t'])}</span> {e(x['text'])}"
                      f"{'' if x['enabled'] else ' <i>(mantida)</i>'}</li>" for x in r["retakes"]) or "<li>Nenhuma</li>"
    fast = "".join(f"<li><span class='t'>{_mmss(x['t'])}</span> {x['wpm']} palavras/min</li>" for x in r["fast"][:8])
    tips = "".join(f"<li>{e(t)}</li>" for t in r["tips"])
    top = ", ".join(f"{e(w)} ({n})" for w, n in r["top_words"])
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Relatório da aula — {e(title)}</title>
<style>
:root{{--bg:#f6f7fb;--card:#fff;--ink:#1d2033;--mut:#6b7089;--acc:#5b5bd6;--line:#e6e8f0}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,Segoe UI,Roboto,sans-serif}}
main{{max-width:900px;margin:0 auto;padding:32px 20px 60px}}h1{{margin:0;font-size:26px}}
.sub{{color:var(--mut);margin:4px 0 24px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin-bottom:14px}}
.kpi .n{{font-size:28px;font-weight:800}}.kpi .l{{color:var(--mut);font-size:13px}}
h2{{font-size:16px;margin:0 0 12px}}ul{{margin:0;padding-left:18px}}li{{margin:3px 0}}
.score{{display:grid;grid-template-columns:110px 1fr 36px;gap:10px;align-items:center;margin:8px 0}}
.track{{height:10px;background:#eef0f6;border-radius:6px;overflow:hidden}}.fill{{height:100%}}.sv{{font-weight:700;text-align:right}}
.big{{font-size:46px;font-weight:800;color:var(--acc);line-height:1}}.t{{font-family:ui-monospace,Consolas,monospace;color:var(--mut);margin-right:6px}}
.chart{{width:100%;height:auto}}.band{{fill:#22c55e22}}.line{{fill:none;stroke:var(--acc);stroke-width:2.5}}.tk{{font-size:10px;fill:var(--mut)}}
.tips li{{margin:8px 0}}.foot{{color:var(--mut);font-size:12px;margin-top:20px}}
</style></head><body><main>
<h1>Relatório da aula</h1><div class="sub">{e(title)} · {_mmss(r['duration'])} gravados → {_mmss(r['final_duration'])} depois da edição</div>
<div class="grid">
<div class="card kpi"><div class="n">{r['wpm']}</div><div class="l">palavras por minuto (ideal {IDEAL_WPM[0]}–{IDEAL_WPM[1]})</div></div>
<div class="card kpi"><div class="n">{sum(r['fillers'].values())}</div><div class="l">vícios ({r['fillers_per_min']:.1f} por minuto)</div></div>
<div class="card kpi"><div class="n">{len(r['retakes'])}</div><div class="l">frases regravadas</div></div>
<div class="card kpi"><div class="n">{r['removed_total']:.0f} s</div><div class="l">tirados na edição</div></div>
</div>
<div class="card"><div style="display:flex;gap:24px;align-items:center;flex-wrap:wrap">
<div><div class="big">{s['geral']}</div><div class="l" style="color:var(--mut)">nota geral</div></div>
<div style="flex:1;min-width:260px">{_bar('Ritmo', s['ritmo'])}{_bar('Fluência', s['fluencia'])}{_bar('Clareza', s['clareza'])}{_bar('Engajamento', s['engajamento'])}</div>
</div></div>
<div class="card tips"><h2>O que melhorar na próxima gravação</h2><ul>{tips}</ul></div>
<div class="card"><h2>Ritmo ao longo da aula</h2>{_chart(r['timeline']) or '<p class="sub">Aula curta demais para o gráfico.</p>'}
{f'<p><b>Trechos rápidos:</b></p><ul>{fast}</ul>' if fast else ''}</div>
<div class="grid">
<div class="card"><h2>Vícios</h2><ul>{fillers}</ul></div>
<div class="card"><h2>Palavras-muleta</h2><ul>{crutches}</ul></div>
<div class="card"><h2>Edição</h2><ul>{removed or '<li>Nada cortado</li>'}</ul></div>
</div>
<div class="card"><h2>Regravações</h2><ul>{retakes}</ul></div>
<div class="card"><h2>Mais números</h2><ul>
<li>{r['questions']} perguntas para a turma ({r['questions_per_10min']:.1f} a cada 10 min)</li>
<li>Maior trecho sem pausa: {r['longest_run']['s']:.0f} s (em {_mmss(r['longest_run']['t'])})</li>
<li>{len(r['long_pauses'])} pausas longas mantidas (demonstrações)</li>
<li>{r['fast_captions']} de {r['captions']} legendas acima da velocidade de leitura</li>
<li>Palavras que mais apareceram: {top or '—'}</li></ul></div>
<p class="foot">Indicadores automáticos calculados a partir da transcrição, não uma avaliação definitiva.
Gerado pelo LUIS MEDIA TOOLS, no seu computador.</p>
</main></body></html>"""
