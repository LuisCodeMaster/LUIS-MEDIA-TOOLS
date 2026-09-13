import sys
import os
import re

def parse_tables(text):
    lines = text.split('\n')
    new_lines = []
    in_table = False
    table_lines = []

    for line in lines:
        if '|' in line and not line.strip().startswith('||'):
            in_table = True
            table_lines.append(line.strip())
        else:
            if in_table:
                new_lines.append(render_table(table_lines))
                table_lines = []
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append(render_table(table_lines))
    return '\n'.join(new_lines)

def render_table(lines):
    if len(lines) < 2:
        return '\n'.join(lines)
    header = [c.strip() for c in lines[0].strip('|').split('|')]
    html = '<div class="table-container"><table><thead><tr>'
    for h in header:
        html += f'<th>{h}</th>'
    html += '</tr></thead><tbody>'
    
    start_idx = 2 if '---' in lines[1] else 1
    for row in lines[start_idx:]:
        cols = [c.strip() for c in row.strip('|').split('|')]
        html += '<tr>'
        for col in cols:
            html += f'<td>{col}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html

def render_markdown(text):
    text = parse_tables(text)

    # Callouts
    text = re.sub(r'\[DICA\]\s*(.*)', r'<div class="callout tip"><div class="callout-header"><span class="icon">💡</span> DICA PRÁTICA</div><p>\1</p></div>', text)
    text = re.sub(r'\[ATENCAO\]\s*(.*)', r'<div class="callout warning"><div class="callout-header"><span class="icon">⚠️</span> ATENÇÃO</div><p>\1</p></div>', text)
    text = re.sub(r'\[INFO\]\s*(.*)', r'<div class="callout info"><div class="callout-header"><span class="icon">📌</span> DESTAQUE</div><p>\1</p></div>', text)
    
    # Speaker notes
    text = re.sub(r'\[NOTA\]\s*(.*)', r'<aside class="speaker-notes"><div class="notes-badge">Anotação do Apresentador</div>\1</aside>', text)

    # Titulos
    text = re.sub(r'^### (.*)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

    # Formatacao inline
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

    # Codigo
    text = re.sub(r'```(\w+)?\n([\s\S]*?)```', r'<div class="code-box"><pre><code>\2</code></pre></div>', text)
    text = re.sub(r'`([^`]+)`', r'<code class="inline-code">\1</code>', text)

    # Colunas em Grid Cards
    text = re.sub(r'\|\|\s*COLUNA', r'</div><div class="col card">', text)
    text = re.sub(r'\|\|\s*FIM', r'</div></div>', text)
    if '</div><div class="col card">' in text:
        text = text.replace('</div><div class="col card">', '<div class="row-grid"><div class="col card">', 1)

    # Listas
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                new_lines.append('<ul class="custom-list">')
                in_list = True
            new_lines.append(f'<li>{line.strip()[2:]}</li>')
        else:
            if in_list:
                new_lines.append('</ul>')
                in_list = False
            new_lines.append(line)
    if in_list:
        new_lines.append('</ul>')
    text = '\n'.join(new_lines)

    # Paragrafos
    paras = text.split('\n\n')
    formatted = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<') and p.endswith('>'):
            formatted.append(p)
        else:
            formatted.append(f'<p>{p}</p>')
    return '\n'.join(formatted)

def build_slides(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
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
<style>
  :root {{
    --bg-main: #090d16;
    --bg-card: rgba(255, 255, 255, 0.04);
    --border-card: rgba(255, 255, 255, 0.08);
    --primary: #38bdf8;
    --primary-glow: rgba(56, 189, 248, 0.25);
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
    height: 100vh;
    width: 100vw;
  }}
  .progress-bar {{
    position: fixed; top: 0; left: 0; height: 4px;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    box-shadow: 0 0 10px var(--primary);
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 100;
  }}
  .deck {{ width: 100vw; height: 100vh; position: relative; }}
  .slide {{
    display: none; width: 100%; height: 100%;
    padding: 60px 90px;
    position: absolute; inset: 0;
    opacity: 0;
    transform: translateY(10px);
    transition: opacity 0.3s ease, transform 0.3s ease;
  }}
  .slide.active {{
    display: flex; flex-direction: column; justify-content: center;
    opacity: 1; transform: translateY(0);
  }}
  .slide-container {{ max-width: 1250px; margin: 0 auto; width: 100%; }}
  h1 {{
    font-size: 3.4rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.15;
    background: linear-gradient(135deg, #ffffff 30%, var(--primary) 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 24px;
  }}
  h2 {{ font-size: 2.3rem; font-weight: 700; letter-spacing: -0.02em; color: #f1f5f9; margin-bottom: 20px; }}
  h3 {{ font-size: 1.4rem; font-weight: 600; color: var(--accent); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 0.05em; }}
  p {{ font-size: 1.25rem; line-height: 1.65; color: var(--text-muted); margin-bottom: 16px; }}
  .row-grid {{ display: flex; gap: 24px; margin-top: 24px; }}
  .card {{
    flex: 1; background: var(--bg-card);
    border: 1px solid var(--border-card);
    backdrop-filter: blur(12px);
    border-radius: 16px; padding: 28px;
    box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
  }}
  .custom-list {{ list-style: none; margin: 18px 0; }}
  .custom-list li {{
    font-size: 1.25rem; color: #e2e8f0; margin-bottom: 12px;
    display: flex; align-items: center; gap: 12px;
  }}
  .custom-list li::before {{
    content: ""; width: 8px; height: 8px; border-radius: 50%;
    background: var(--primary); box-shadow: 0 0 8px var(--primary);
    flex-shrink: 0;
  }}
  .callout {{
    border-radius: 12px; padding: 18px 22px; margin: 20px 0;
    backdrop-filter: blur(8px);
  }}
  .callout-header {{ font-weight: 700; font-size: 0.95rem; letter-spacing: 0.05em; margin-bottom: 6px; display: flex; align-items: center; gap: 8px; }}
  .callout p {{ font-size: 1.1rem; color: #f8fafc; margin: 0; }}
  .callout.tip {{ background: rgba(56, 189, 248, 0.08); border-left: 4px solid var(--primary); }}
  .callout.tip .callout-header {{ color: var(--primary); }}
  .callout.warning {{ background: rgba(245, 158, 11, 0.08); border-left: 4px solid #f59e0b; }}
  .callout.warning .callout-header {{ color: #fbbf24; }}
  .code-box {{
    background: #040711; border: 1px solid #1e293b;
    border-radius: 12px; padding: 20px; margin: 20px 0;
    box-shadow: inset 0 2px 10px rgba(0,0,0,0.4);
  }}
  pre {{ font-family: var(--font-mono); font-size: 1.05rem; line-height: 1.5; color: #38bdf8; overflow-x: auto; }}
  .inline-code {{ font-family: var(--font-mono); background: rgba(255,255,255,0.08); padding: 3px 7px; border-radius: 6px; color: #38bdf8; font-size: 0.95em; }}
  .table-container {{ margin: 20px 0; border-radius: 12px; overflow: hidden; border: 1px solid var(--border-card); }}
  table {{ width: 100%; border-collapse: collapse; text-align: left; background: var(--bg-card); }}
  th {{ background: rgba(255,255,255,0.05); color: var(--primary); padding: 14px 18px; font-weight: 600; border-bottom: 1px solid var(--border-card); }}
  td {{ padding: 14px 18px; color: #e2e8f0; border-bottom: 1px solid rgba(255,255,255,0.03); }}
  .speaker-notes {{
    display: none; background: #111827; border: 1px solid #374151;
    border-radius: 10px; padding: 16px; margin-top: 24px; color: #cbd5e1; font-size: 1rem;
  }}
  .notes-badge {{
    font-size: 0.75rem; text-transform: uppercase; font-weight: 700;
    color: #a855f7; margin-bottom: 4px; letter-spacing: 0.08em;
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
    padding: 6px 14px; font-family: var(--font-mono); font-size: 0.85rem; color: #94a3b8;
  }}
  .deck.overview {{ display: flex; flex-wrap: wrap; overflow-y: auto; gap: 24px; padding: 50px; background: #020617; }}
  .deck.overview .slide {{
    display: block !important; position: relative !important;
    width: calc(33.333% - 16px) !important; height: 260px !important;
    border: 1px solid var(--border-card); border-radius: 14px;
    transform: scale(0.98); cursor: pointer; padding: 25px; overflow: hidden;
  }}
  @media print {{
    body {{ background: #fff !important; color: #000 !important; overflow: visible; }}
    .slide {{ display: block !important; position: relative !important; page-break-after: always; height: 100vh; }}
    .progress-bar, .timer-badge, .slide-footer {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="progress-bar" id="progress"></div>
<div class="timer-badge" id="timer">00:00</div>
<div class="deck" id="deck">
{slides_html}
</div>
<script>
  const slides = document.querySelectorAll('.slide');
  let current = 0;
  function update() {{
    slides.forEach((s, idx) => s.classList.toggle('active', idx === current));
    document.getElementById('progress').style.width = ((current + 1) / slides.length * 100) + '%';
  }}
  document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowRight' || e.key === ' ') {{
      if (current < slides.length - 1) current++;
      update();
    }} else if (e.key === 'ArrowLeft') {{
      if (current > 0) current--;
      update();
    }} else if (e.key.toLowerCase() === 'o') {{
      document.getElementById('deck').classList.toggle('overview');
    }} else if (e.key.toLowerCase() === 'n') {{
      document.body.classList.toggle('show-notes');
    }} else if (e.key.toLowerCase() === 'p') {{
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

    out_file = os.path.splitext(md_path)[0] + '.html'
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f"[OK] Slides compilados em: {out_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        build_slides(sys.argv[1])
    else:
        build_slides("slides/roteiro-aula.md")