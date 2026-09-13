import sys
import os
import re

def render_markdown(text):
    # Dicas e Atencao
    text = re.sub(r'\[DICA\]\s*(.*)', r'<div class="callout tip"><div class="callout-title">💡 DICA</div><p>\1</p></div>', text)
    text = re.sub(r'\[ATENCAO\]\s*(.*)', r'<div class="callout warning"><div class="callout-title">⚠️ ATENÇÃO</div><p>\1</p></div>', text)
    
    # Notas do apresentador
    text = re.sub(r'\[NOTA\]\s*(.*)', r'<aside class="speaker-notes"><strong>Nota:</strong> \1</aside>', text)

    # Titulos
    text = re.sub(r'^### (.*)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

    # Negrito e Italico
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

    # Blocos de codigo
    text = re.sub(r'```(\w+)?\n([\s\S]*?)```', r'<pre><code>\2</code></pre>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Colunas
    text = re.sub(r'\|\|\s*COLUNA', r'</div><div class="col">', text)
    text = re.sub(r'\|\|\s*FIM', r'</div></div>', text)
    if '</div><div class="col">' in text:
        text = text.replace('</div><div class="col">', '<div class="row"><div class="col">', 1)

    # Listas
    lines = text.split('\n')
    in_list = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('- ') or line.strip().startswith('* '):
            if not in_list:
                new_lines.append('<ul>')
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
    formatted_paras = []
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if p.startswith('<') and p.endswith('>'):
            formatted_paras.append(p)
        else:
            formatted_paras.append(f'<p>{p}</p>')
    return '\n'.join(formatted_paras)

def build_slides(md_path):
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    raw_slides = re.split(r'\n---\n', content)
    slides_html = ""
    for idx, raw in enumerate(raw_slides, 1):
        parsed = render_markdown(raw.strip())
        slides_html += f'<section class="slide" id="slide-{idx}"><div class="slide-content">{parsed}</div><div class="slide-number">{idx} / {len(raw_slides)}</div></section>\n'

    html_template = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apresentação - LUIS MEDIA TOOLS</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; overflow: hidden; }}
  .deck {{ width: 100vw; height: 100vh; position: relative; }}
  .slide {{ display: none; width: 100%; height: 100%; padding: 60px 80px; position: absolute; inset: 0; }}
  .slide.active {{ display: flex; flex-direction: column; justify-content: center; }}
  .slide-content {{ max-width: 1200px; margin: 0 auto; width: 100%; }}
  h1 {{ font-size: 3rem; margin-bottom: 20px; color: #38bdf8; }}
  h2 {{ font-size: 2.2rem; margin-bottom: 20px; color: #f1f5f9; }}
  h3 {{ font-size: 1.5rem; margin-bottom: 15px; color: #94a3b8; }}
  p {{ font-size: 1.3rem; line-height: 1.6; margin-bottom: 15px; color: #cbd5e1; }}
  ul {{ margin-left: 30px; font-size: 1.3rem; line-height: 1.6; margin-bottom: 15px; color: #cbd5e1; }}
  li {{ margin-bottom: 8px; }}
  .row {{ display: flex; gap: 40px; margin-top: 20px; }}
  .col {{ flex: 1; }}
  .callout {{ padding: 15px 20px; border-radius: 8px; margin: 20px 0; }}
  .callout.tip {{ background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; }}
  .callout.warning {{ background: rgba(245, 158, 11, 0.1); border-left: 4px solid #f59e0b; }}
  .callout-title {{ font-weight: bold; margin-bottom: 5px; }}
  .speaker-notes {{ display: none; background: #1e293b; padding: 15px; border-radius: 6px; border-left: 4px solid #a855f7; margin-top: 20px; color: #e2e8f0; font-size: 1rem; }}
  body.show-notes .speaker-notes {{ display: block; }}
  pre {{ background: #020617; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 15px 0; border: 1px solid #334155; }}
  code {{ font-family: Consolas, monospace; color: #38bdf8; }}
  .progress-bar {{ position: fixed; top: 0; left: 0; height: 5px; background: #38bdf8; transition: width 0.3s ease; }}
  .slide-number {{ position: absolute; bottom: 20px; right: 40px; font-size: 0.9rem; color: #64748b; }}
  .timer {{ position: absolute; bottom: 20px; left: 40px; font-size: 0.9rem; color: #64748b; font-family: monospace; }}
  .deck.overview {{ display: flex; flex-wrap: wrap; overflow-y: auto; gap: 20px; padding: 40px; }}
  .deck.overview .slide {{ display: block !important; position: relative !important; width: calc(33.333% - 20px) !important; height: 240px !important; border: 2px solid #334155; border-radius: 8px; transform: scale(0.95); cursor: pointer; }}
  @media print {{
    body {{ overflow: visible; background: #fff; color: #000; }}
    .slide {{ display: block !important; position: relative !important; page-break-after: always; height: 100vh; }}
    .progress-bar, .timer {{ display: none; }}
  }}
</style>
</head>
<body>
<div class="progress-bar" id="progress"></div>
<div class="deck" id="deck">
{slides_html}
</div>
<div class="timer" id="timer">00:00</div>
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