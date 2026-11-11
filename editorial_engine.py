import sys, os, json, re
from html import escape

def format_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"

def processar_editorial(pasta_aula):
    pasta_docs = os.path.join(pasta_aula, "6_Documentos")
    pasta_whisper = os.path.join(pasta_aula, "5_Dados_Whisper")
    pasta_slides = os.path.join(pasta_docs, "slides_extraidos")

    if not os.path.exists(pasta_docs):
        os.makedirs(pasta_docs, exist_ok=True)

    nome_aula = escape(os.path.basename(os.path.normpath(pasta_aula)))
    
    # Busca arquivos de imagem extraidos
    imagens = []
    if os.path.exists(pasta_slides):
        for f in sorted(os.listdir(pasta_slides)):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                # Extrai timestamp aproximado do nome do arquivo se houver (ex: frame_0012.34.png)
                match = re.search(r"frame_(\d+[\.\d]*)", f)
                ts = float(match.group(1)) if match else 0.0
                imagens.append({
                    "arquivo": os.path.join("slides_extraidos", f).replace("\\", "/"),
                    "timestamp": ts
                })

    # Busca arquivos JSON do Whisper para resgatar texto com minutagem
    segmentos = []
    if os.path.exists(pasta_whisper):
        for f in sorted(os.listdir(pasta_whisper)):
            if f.lower().endswith(".json"):
                caminho_json = os.path.join(pasta_whisper, f)
                try:
                    with open(caminho_json, "r", encoding="utf-8") as jf:
                        dados = json.load(jf)
                        for seg in dados.get("segments", []):
                            segmentos.append({
                                "start": seg.get("start", 0),
                                "text": escape(seg.get("text", "").strip())
                            })
                except Exception as e:
                    print(f"[AVISO] Erro ao ler {f}: {e}")

    # Monta os blocos da apostila didatica
    blocos_html = []
    
    if imagens:
        # Cruza imagens com trechos de fala
        for i, img in enumerate(imagens):
            t_inicio = img["timestamp"]
            t_fim = imagens[i+1]["timestamp"] if i+1 < len(imagens) else 999999.0
            
            falas = [s["text"] for s in segmentos if t_inicio <= s["start"] < t_fim]
            texto_bloco = " ".join(falas) if falas else "<em>Explicação visual demonstrada na tela pelo professor.</em>"
            
            blocos_html.append(f"""
            <div class="bloco-didatico">
                <div class="tempo-tag">Momento: {format_time(t_inicio)}</div>
                <div class="slide-container">
                    <img src="{img['arquivo']}" alt="Slide {i+1}" />
                </div>
                <div class="texto-didatico">
                    <p>{texto_bloco}</p>
                </div>
            </div>
            """)
    else:
        # Fallback sem imagens: renderiza a transcricao em paragrafos limpos
        texto_geral = " ".join([s["text"] for s in segmentos])
        blocos_html.append(f"""
        <div class="bloco-didatico">
            <div class="texto-didatico">
                <p>{texto_geral}</p>
            </div>
        </div>
        """)

    html_apostila = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apostila Editorial - {nome_aula}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #f8fafc;
    color: #1e293b;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    line-height: 1.7;
    padding: 40px 20px;
  }}
  .documento {{
    max-width: 900px;
    margin: 0 auto;
    background: #ffffff;
    padding: 60px 80px;
    border-radius: 12px;
    box-shadow: 0 4px 25px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
  }}
  header.capa {{
    border-bottom: 2px solid #0f172a;
    padding-bottom: 30px;
    margin-bottom: 40px;
  }}
  h1 {{ font-size: 2.4rem; color: #0f172a; margin-bottom: 8px; font-weight: 800; }}
  .subtitulo {{ font-size: 1.1rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
  .bloco-didatico {{
    margin-bottom: 50px;
    page-break-inside: avoid;
  }}
  .tempo-tag {{
    display: inline-block;
    background: #eff6ff;
    color: #2563eb;
    border: 1px solid #bfdbfe;
    font-size: 0.85rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 6px;
    margin-bottom: 12px;
  }}
  .slide-container {{
    margin: 12px 0 20px 0;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #cbd5e1;
    background: #0f172a;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
  }}
  .slide-container img {{
    width: 100%;
    display: block;
    height: auto;
  }}
  .texto-didatico p {{
    font-size: 1.15rem;
    color: #334155;
    text-align: justify;
    line-height: 1.8;
  }}
  footer {{
    margin-top: 60px;
    border-top: 1px solid #e2e8f0;
    padding-top: 20px;
    font-size: 0.9rem;
    color: #94a3b8;
    display: flex;
    justify-content: space-between;
  }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .documento {{ border: none; box-shadow: none; padding: 0; max-width: 100%; }}
    .bloco-didatico {{ page-break-inside: avoid; margin-bottom: 40px; }}
  }}
</style>
</head>
<body>
<div class="documento">
  <header class="capa">
    <div class="subtitulo">Material Didático e Editorial</div>
    <h1>{nome_aula}</h1>
    <p style="color: #64748b; font-size: 0.95rem;">Compilado automaticamente pelo LUIS MEDIA TOOLS</p>
  </header>
  
  {"".join(blocos_html)}

  <footer>
    <span>LUIS MEDIA TOOLS — Ecossistema Editorial</span>
    <span>Página Didática Oficial</span>
  </footer>
</div>
</body>
</html>"""

    arquivo_saida = os.path.join(pasta_docs, "apostila-ilustrada.html")
    with open(arquivo_saida, "w", encoding="utf-8") as f:
        f.write(html_apostila)
    print(f"[OK] Apostila Didática Ilustrada gerada em: {arquivo_saida}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_editorial(sys.argv[1])
    else:
        print("[ERRO] Informe o caminho da pasta da aula.")