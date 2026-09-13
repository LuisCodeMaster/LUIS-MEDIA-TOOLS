import sys
import os
import json
import re
import subprocess
import urllib.request

def chamar_ollama(prompt, model="llama3.2:3b"):
    url = "http://localhost:11434/api/generate"
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("response", "")
    except Exception as e:
        print(f"    [ERRO OLLAMA] Nao foi possivel comunicar com o Llama: {e}")
        return None

def srt_para_texto(caminho_srt):
    blocos = []
    if not os.path.exists(caminho_srt):
        return blocos
    with open(caminho_srt, "r", encoding="utf-8", errors="ignore") as f:
        conteudo = f.read()

    # Regex para capturar timestamp e texto
    padrao = re.compile(r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)", re.DOTALL)
    for match in padrao.finditer(conteudo):
        idx, t_in, t_out, txt = match.groups()
        blocos.append({
            "in": t_in.replace(",", "."),
            "out": t_out.replace(",", "."),
            "txt": txt.strip().replace("\n", " ")
        })
    return blocos

def timecode_para_segundos(tc):
    partes = tc.split(":")
    h = float(partes[0])
    m = float(partes[1])
    s = float(partes[2])
    return h * 3600 + m * 60 + s

def identificar_melhores_momentos(blocos):
    amostra_srt = ""
    for b in blocos:
        amostra_srt += f"[{b['in']} -> {b['out']}] {b['txt']}\n"
    
    # Limita tamanho para a CPU rodar rápido
    amostra_srt = amostra_srt[:14000]

    prompt = f"""Voce e um especialista em marketing de conteudo e editor de cortes para TikTok, Reels e Shorts.
Analise a transcricao com timestamps abaixo e selecione os 3 trechos mais impactantes, diretos e interessantes para video curto (duracao de cada trecho entre 25 e 60 segundos).

Retorne OBRIGATORIAMENTE um JSON com a seguinte chave:
{{
  "cortes": [
    {{
      "titulo": "Titulo chamativo sem acentos ou caracteres especiais",
      "inicio": "00:00:00.000",
      "fim": "00:00:35.000"
    }}
  ]
}}

Transcricao:
{amostra_srt}
"""
    resposta = chamar_ollama(prompt)
    if not resposta:
        return []

    try:
        dados = json.loads(resposta)
        return dados.get("cortes", [])
    except Exception:
        # Fallback de seguranca caso o JSON venha truncado
        return []

def extrair_srt_parcial(caminho_srt_orig, start_sec, end_sec, caminho_srt_dest):
    blocos = srt_para_texto(caminho_srt_orig)
    idx = 1
    with open(caminho_srt_dest, "w", encoding="utf-8") as f:
        for b in blocos:
            s_in = timecode_para_segundos(b["in"])
            s_out = timecode_para_segundos(b["out"])
            if s_out >= start_sec and s_in <= end_sec:
                # Ajusta timestamp relativo ao inicio do corte (t=0)
                rel_in = max(0.0, s_in - start_sec)
                rel_out = min(end_sec - start_sec, s_out - start_sec)
                
                h1, m1, s1 = int(rel_in // 3600), int((rel_in % 3600) // 60), rel_in % 60
                h2, m2, s2 = int(rel_out // 3600), int((rel_out % 3600) // 60), rel_out % 60
                
                tc1 = f"{h1:02d}:{m1:02d}:{s1:06.3f}".replace(".", ",")
                tc2 = f"{h2:02d}:{m2:02d}:{s2:06.3f}".replace(".", ",")
                f.write(f"{idx}\n{tc1} --> {tc2}\n{b['txt']}\n\n")
                idx += 1

def renderizar_corte_vertical(video_orig, start_tc, end_tc, srt_corte, video_saida):
    start_sec = timecode_para_segundos(start_tc)
    end_sec = timecode_para_segundos(end_tc)
    duracao = end_sec - start_sec
    if duracao <= 5:
        return

    srt_escapado = srt_corte.replace("\\", "/").replace(":", "\\:")
    estilo = "FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,MarginV=120"

    # Layout Vertical: Fundo 1080x1920 com Blur + Vídeo proporcional centralizado + Legenda
    filtro_complexo = (
        f"[0:v]split=2[bg_in][fg_in];"
        f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];"
        f"[fg_in]scale=1080:608:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]subtitles='{srt_escapado}':force_style='{estilo}'[v]"
    )

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duracao:.3f}",
        "-i", video_orig,
        "-filter_complex", filtro_complexo,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "faster", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        video_saida
    ]
    subprocess.run(cmd)

def processar_cortes(dir_saida):
    pasta_cortes = os.path.join(dir_saida, "Cortes_9x16")
    if not os.path.exists(pasta_cortes):
        os.makedirs(pasta_cortes, exist_ok=True)

    # 1. Encontrar o vídeo preferencial (DINAMICO ou o primeiro original disponível)
    video_alvo = None
    for arq in os.listdir(dir_saida):
        if arq.endswith("_DINAMICO.mp4"):
            video_alvo = os.path.join(dir_saida, arq)
            break

    if not video_alvo:
        for arq in os.listdir(dir_saida):
            if arq.endswith(".mp4") and not arq.endswith("_LEGENDADO.mp4"):
                video_alvo = os.path.join(dir_saida, arq)
                break

    if not video_alvo:
        print("    [AVISO] Nenhum video encontrado para gerar cortes.")
        return

    # 2. Localizar a legenda correspondente
    pasta_legendas = os.path.join(dir_saida, "1_Legendas")
    if not os.path.exists(pasta_legendas):
        print("    [AVISO] Pasta de legendas nao encontrada.")
        return

    srts = [os.path.join(pasta_legendas, f) for f in os.listdir(pasta_legendas) if f.endswith(".srt")]
    if not srts:
        print("    [AVISO] Nenhuma legenda encontrada.")
        return

    srt_principal = srts[0]
    blocos = srt_para_texto(srt_principal)
    if not blocos:
        return

    print("    [IA] Llama analisando transcricao para encontrar os 3 melhores momentos...")
    melhores = identificar_melhores_momentos(blocos)

    if not melhores:
        # Fallback caso a aula seja curta ou a resposta falhe: pega os primeiros 35 segundos
        melhores = [{
            "titulo": "Momento_Principal",
            "inicio": blocos[0]["in"],
            "fim": blocos[min(len(blocos)-1, 15)]["out"]
        }]

    print(f"    [OK] {len(melhores)} corte(s) de alto engajamento mapeados!")

    for i, corte in enumerate(melhores, start=1):
        t_ini = corte.get("inicio", "00:00:00.000")
        t_fim = corte.get("fim", "00:00:35.000")
        titulo_limpo = re.sub(r"[^\w\s-]", "", corte.get("titulo", f"Corte_{i}")).strip().replace(" ", "_")
        
        nome_corte = f"Corte_{i}_{titulo_limpo}.mp4"
        caminho_final_corte = os.path.join(pasta_cortes, nome_corte)
        caminho_srt_temp = os.path.join(pasta_cortes, f"temp_{i}.srt")

        print(f"    [RENDER 9:16] Gerando Clipes #{i}: {titulo_limpo} ({t_ini} -> {t_fim})...")
        s_in = timecode_para_segundos(t_ini)
        s_out = timecode_para_segundos(t_fim)
        
        extrair_srt_parcial(srt_principal, s_in, s_out, caminho_srt_temp)
        renderizar_corte_vertical(video_alvo, t_ini, t_fim, caminho_srt_temp, caminho_final_corte)

        if os.path.exists(caminho_srt_temp):
            os.remove(caminho_srt_temp)

    print(f"    [SUCESSO] Cortes verticais salvos em: {pasta_cortes}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_cortes(sys.argv[1])
