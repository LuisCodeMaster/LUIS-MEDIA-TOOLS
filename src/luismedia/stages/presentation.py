"""Apresentacoes: roteiro em Markdown (escrito pela IA ou pelo usuario) -> HTML 16:9 interativo.

Porte do slides_engine.py para o pacote: mesmo visual e atalhos (setas, L laser, D desenho,
O visao geral, N notas, P imprimir/PDF), agora com o texto escapado e geracao pela IA.
"""

import html as _html
import os
import re
from pathlib import Path


def render_markdown(text):
    # Padronizar quebras de linha Windows/Linux
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 1. Capturar e isolar blocos de codigo (aceita ```bash, ``` e variacoes)
    code_blocks = []
    def save_code(m):
        lang = m.group(1) or 'bash'
        code = m.group(2).strip()
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        idx = len(code_blocks)
        html = f'<div class="code-box"><div class="code-header"><span class="code-dot"></span><span class="code-dot"></span><span class="code-dot"></span><span class="code-lang">{lang}</span></div><pre><code class="language-{lang}">{code}</code></pre></div>'
        code_blocks.append(html)
        return f"%%CODEBLOCK_{idx}%%"

    text = re.sub(r'```(?:([a-zA-Z0-9_-]+))?\n([\s\S]*?)```', save_code, text)

    # Texto comum escapado (um '<' vindo da IA nao quebra a pagina); codigo ja foi protegido
    text = _html.escape(text, quote=False)

    # 2. Callouts e Notas
    text = re.sub(r'\[DICA\]\s*(.*)', r'<div class="callout tip"><div class="callout-header">💡 DICA PRÁTICA</div><p>\1</p></div>', text)
    text = re.sub(r'\[ATENCAO\]\s*(.*)', r'<div class="callout warning"><div class="callout-header">⚠️ ATENÇÃO</div><p>\1</p></div>', text)
    text = re.sub(r'\[INFO\]\s*(.*)', r'<div class="callout info"><div class="callout-header">📌 DESTAQUE</div><p>\1</p></div>', text)
    text = re.sub(r'\[NOTA\]\s*(.*)', r'<aside class="speaker-notes"><div class="notes-badge">Anotação do Apresentador</div>\1</aside>', text)

    # 3. Titulos (apenas fora de blocos de codigo)
    text = re.sub(r'^### (.*)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

    # 4. Formatacao inline basica
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text)

    # 5. Colunas
    text = re.sub(r'\|\|\s*COLUNA', r'</div><div class="col card">', text)
    text = re.sub(r'\|\|\s*FIM', r'</div></div>', text)
    if '</div><div class="col card">' in text:
        text = text.replace('</div><div class="col card">', '<div class="row-grid"><div class="col card">', 1)

    # 6. Listas com alinhamento corrigido
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                new_lines.append('<ul class="custom-list">')
                in_list = True
            item_text = line.strip()[2:]
            new_lines.append(f'<li><span class="bullet-dot"></span><div class="bullet-content">{item_text}</div></li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    text = '\n'.join(new_lines)

    # 7. Paragrafos
    paras = text.split('\n\n')
    formatted = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<') or '%%CODEBLOCK_' in p:
            formatted.append(p)
        else:
            formatted.append(f'<p>{p}</p>')
    text = '\n'.join(formatted)

    # 8. Restaurar blocos de codigo protegidos
    for idx, block in enumerate(code_blocks):
        text = text.replace(f'<p>%%CODEBLOCK_{idx}%%</p>', block)
        text = text.replace(f'%%CODEBLOCK_{idx}%%', block)

    return text

def build_slides(md_path, out_file=None):
    if not os.path.exists(md_path):
        raise FileNotFoundError(md_path)

    with open(md_path, encoding='utf-8') as f:
        content = f.read()

    raw_slides = re.split(r'\n---\n', content)
    slides_html = ""
    for idx, raw in enumerate(raw_slides, 1):
        parsed = render_markdown(raw.strip())
        slides_html += f'''
        <section class="slide" id="slide-{idx}">
            <div class="slide-container">
                <div class="slide-content">{parsed}</div>
            </div>
            <div class="slide-footer">
                <span class="project-tag">LUIS MEDIA TOOLS</span>
                <span class="slide-counter">{idx} <small>/ {len(raw_slides)}</small></span>
            </div>
        </section>'''

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apresentação - LUIS MEDIA TOOLS</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<style>
  :root {{
    --bg-main: #090d16;
    --bg-card: rgba(255, 255, 255, 0.04);
    --border-card: rgba(255, 255, 255, 0.08);
    --primary: #38bdf8;
    --accent: #818cf8;
    --text-main: #f8fafc;
    --text-muted: #94a3b8;
    --font-sans: 'Plus Jakarta Sans', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: var(--font-sans);
    background: radial-gradient(circle at 15% 15%, #172554 0%, var(--bg-main) 70%);
    color: var(--text-main);
    overflow: hidden;
    height: 100vh; width: 100vw;
  }}
  .progress-bar {{
    position: fixed; top: 0; left: 0; height: 4px;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    box-shadow: 0 0 10px var(--primary);
    transition: width 0.3s ease; z-index: 100;
  }}
  .deck {{ width: 100vw; height: 100vh; position: relative; }}
  .slide {{
    display: none; width: 100%; height: 100%;
    padding: 60px 90px; position: absolute; inset: 0;
    opacity: 0; transform: translateY(10px);
    transition: opacity 0.3s ease, transform 0.3s ease;
  }}
  .slide.active {{
    display: flex; flex-direction: column; justify-content: center;
    opacity: 1; transform: translateY(0);
  }}
  .slide-container {{ max-width: 1250px; margin: 0 auto; width: 100%; }}
  h1 {{
    font-size: 3.2rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.15;
    background: linear-gradient(135deg, #ffffff 30%, var(--primary) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 20px;
  }}
  h2 {{ font-size: 2.2rem; font-weight: 700; color: #f1f5f9; margin-bottom: 16px; }}
  h3 {{ font-size: 1.25rem; font-weight: 700; color: var(--accent); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.05em; }}
  p {{ font-size: 1.2rem; line-height: 1.6; color: var(--text-muted); margin-bottom: 16px; }}
  .row-grid {{ display: flex; gap: 24px; margin-top: 20px; }}
  .card {{
    flex: 1; background: var(--bg-card);
    border: 1px solid var(--border-card);
    backdrop-filter: blur(12px); border-radius: 16px; padding: 24px;
  }}
  .custom-list {{ list-style: none; margin: 12px 0; }}
  .custom-list li {{
    font-size: 1.15rem; color: #e2e8f0; margin-bottom: 12px;
    display: flex; align-items: flex-start; gap: 10px;
  }}
  .bullet-dot {{
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--primary); box-shadow: 0 0 8px var(--primary);
    margin-top: 10px; flex-shrink: 0;
  }}
  .bullet-content {{ flex: 1; line-height: 1.5; }}
  .callout {{
    border-radius: 12px; padding: 16px 20px; margin: 20px 0;
    backdrop-filter: blur(8px);
  }}
  .callout-header {{ font-weight: 700; font-size: 0.95rem; margin-bottom: 6px; }}
  .callout.tip {{ background: rgba(56, 189, 248, 0.08); border-left: 4px solid var(--primary); }}
  .callout.tip .callout-header {{ color: var(--primary); }}
  .callout.warning {{ background: rgba(245, 158, 11, 0.08); border-left: 4px solid #f59e0b; }}
  .callout.warning .callout-header {{ color: #fbbf24; }}
  .callout.info {{ background: rgba(129, 140, 248, 0.08); border-left: 4px solid var(--accent); }}
  .callout.info .callout-header {{ color: var(--accent); }}
  .code-box {{
    background: #090d16; border: 1px solid #1e293b;
    border-radius: 12px; overflow: hidden; margin: 24px 0;
    box-shadow: 0 10px 30px rgba(0,0,0,0.6);
  }}
  .code-header {{
    background: #0f172a; padding: 10px 16px; display: flex;
    align-items: center; gap: 8px; border-bottom: 1px solid #1e293b;
  }}
  .code-dot {{ width: 10px; height: 10px; border-radius: 50%; background: #334155; }}
  .code-dot:nth-child(1) {{ background: #ef4444; }}
  .code-dot:nth-child(2) {{ background: #eab308; }}
  .code-dot:nth-child(3) {{ background: #22c55e; }}
  .code-lang {{ margin-left: auto; font-family: var(--font-mono); font-size: 0.75rem; color: #64748b; text-transform: uppercase; }}
  pre {{ margin: 0; }}
  pre code {{ font-family: var(--font-mono) !important; font-size: 1.05rem; line-height: 1.6; padding: 20px !important; background: transparent !important; display: block; }}
  .inline-code {{ font-family: var(--font-mono); background: rgba(255,255,255,0.08); padding: 3px 7px; border-radius: 6px; color: #38bdf8; font-size: 0.95em; }}
  .speaker-notes {{
    display: none; background: #111827; border: 1px solid #374151;
    border-radius: 10px; padding: 16px; margin-top: 24px; color: #cbd5e1; font-size: 1rem;
  }}
  .notes-badge {{
    font-size: 0.75rem; text-transform: uppercase; font-weight: 700;
    color: #a855f7; margin-bottom: 4px;
  }}
  body.show-notes .speaker-notes {{ display: block; }}
  .slide-footer {{
    position: absolute; bottom: 30px; left: 90px; right: 90px;
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.05); padding-top: 15px;
  }}
  .project-tag {{ font-size: 0.85rem; font-weight: 700; color: #475569; letter-spacing: 0.1em; }}
  .slide-counter {{ font-family: var(--font-mono); font-size: 1rem; color: #64748b; }}
  .timer-badge {{
    position: fixed; top: 18px; right: 30px; background: rgba(15, 23, 42, 0.8);
    border: 1px solid var(--border-card); border-radius: 20px;
    padding: 6px 14px; font-family: var(--font-mono); font-size: 0.85rem; color: #94a3b8; z-index: 101;
  }}
  .deck.overview {{ display: flex; flex-wrap: wrap; overflow-y: auto; gap: 24px; padding: 50px; background: #020617; }}
  .deck.overview .slide {{
    display: block !important; position: relative !important;
    width: calc(33.333% - 16px) !important; height: 260px !important;
    border: 1px solid var(--border-card); border-radius: 14px;
    cursor: pointer; padding: 25px; overflow: hidden;
  }}
  #laser-pointer {{
    position: fixed; width: 22px; height: 22px; border-radius: 50%;
    background: #ef4444; box-shadow: 0 0 14px 4px #ef4444, 0 0 28px #ef4444;
    pointer-events: none; z-index: 9999; display: none; transform: translate(-50%, -50%);
  }}
  #drawing-canvas {{ position: fixed; inset: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 500; }}
  body.drawing-mode #drawing-canvas {{ pointer-events: auto; cursor: crosshair; }}
  @media print {{
    body {{ background: #fff !important; color: #000 !important; overflow: visible; }}
    .slide {{ display: block !important; position: relative !important; page-break-after: always; height: 100vh; }}
    .progress-bar, .timer-badge, .slide-footer, #laser-pointer, #drawing-canvas {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="progress-bar" id="progress"></div>
<div class="timer-badge" id="timer">00:00</div>
<div id="laser-pointer"></div>
<canvas id="drawing-canvas"></canvas>
<div class="deck" id="deck">
{slides_html}
</div>
<script>
  hljs.highlightAll();
  const slides = document.querySelectorAll('.slide');
  let current = 0;
  function update() {{
    slides.forEach((s, idx) => s.classList.toggle('active', idx === current));
    document.getElementById('progress').style.width = ((current + 1) / slides.length * 100) + '%';
  }}
  const laser = document.getElementById('laser-pointer');
  let laserActive = false;
  document.addEventListener('mousemove', (e) => {{
    if (laserActive) {{
      laser.style.left = e.clientX + 'px';
      laser.style.top = e.clientY + 'px';
    }}
  }});
  const canvas = document.getElementById('drawing-canvas');
  const ctx = canvas.getContext('2d');
  function resizeCanvas() {{
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }}
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  let isDrawing = false;
  let drawMode = false;
  canvas.addEventListener('mousedown', (e) => {{
    if (!drawMode) return;
    isDrawing = true;
    ctx.beginPath();
    ctx.moveTo(e.clientX, e.clientY);
  }});
  canvas.addEventListener('mousemove', (e) => {{
    if (!isDrawing || !drawMode) return;
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#38bdf8';
    ctx.shadowBlur = 8;
    ctx.shadowColor = '#38bdf8';
    ctx.lineTo(e.clientX, e.clientY);
    ctx.stroke();
  }});
  canvas.addEventListener('mouseup', () => isDrawing = false);

  document.addEventListener('keydown', (e) => {{
    const key = e.key.toLowerCase();
    if (key === 'l') {{
      laserActive = !laserActive;
      laser.style.display = laserActive ? 'block' : 'none';
    }} else if (key === 'd') {{
      drawMode = !drawMode;
      document.body.classList.toggle('drawing-mode', drawMode);
    }} else if (key === 'e') {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }} else if (e.key === 'ArrowRight' || e.key === ' ') {{
      if (current < slides.length - 1) current++;
      update();
    }} else if (e.key === 'ArrowLeft') {{
      if (current > 0) current--;
      update();
    }} else if (key === 'o') {{
      document.getElementById('deck').classList.toggle('overview');
    }} else if (key === 'n') {{
      document.body.classList.toggle('show-notes');
    }} else if (key === 'p') {{
      window.print();
    }}
  }});

  slides.forEach((s, idx) => {{
    s.addEventListener('click', () => {{
      if (document.getElementById('deck').classList.contains('overview')) {{
        current = idx;
        document.getElementById('deck').classList.remove('overview');
        update();
      }}
    }});
  }});

  let sec = 0;
  setInterval(() => {{
    sec++;
    const m = String(Math.floor(sec / 60)).padStart(2, '0');
    const s = String(sec % 60).padStart(2, '0');
    document.getElementById('timer').innerText = m + ':' + s;
  }}, 1000);
  update();
</script>
</body>
</html>"""

    out_file = str(out_file or (os.path.splitext(md_path)[0] + '.html'))
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html_template)
    return Path(out_file)


SYSTEM_SLIDES = """Voce e um professor e designer instrucional especialista.
Crie uma apresentacao didatica em Markdown baseada no tema pedido.

REGRAS ESTRITAS DE FORMATO:
1. Separe cada slide EXCLUSIVAMENTE com uma linha contendo: ---
2. O primeiro slide DEVE ter esta estrutura:
   # Titulo da Aula
   ### Subtitulo
   **Professor**
3. Para dividir conteudos em colunas paralelas:
   || COLUNA
   topicos coluna 1
   || COLUNA
   topicos coluna 2
   || FIM
4. Use caixas de destaque quando util:
   [DICA] Texto da dica
   [ATENCAO] Texto de aviso
5. Use notas para o apresentador em slides-chave:
   [NOTA] Observacao que nao aparece na tela principal
6. Blocos de codigo devem usar sintaxe padrao: ```linguagem ... ```
7. Escreva em Portugues do Brasil. NAO inclua explicacoes antes ou depois, responda APENAS com o Markdown."""


def generate_markdown(client, topic, n_slides=(5, 7)):
    """Pede o roteiro ao LLM local e limpa cercas de codigo externas."""
    text = client.generate(f"Crie entre {n_slides[0]} e {n_slides[1]} slides didaticos sobre o tema: {topic}",
                           system=SYSTEM_SLIDES).strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip()
