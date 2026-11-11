import sys
import os
import json
import re
import subprocess
import urllib.request

TIMEOUT_S = 300

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
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("response", "")
    except Exception as e:
        return None

def srt_para_texto(caminho_srt):
    blocos = []
    if not os.path.exists(caminho_srt):
        return blocos
    with open(caminho_srt, "r", encoding="utf-8", errors="ignore") as f:
        conteudo = f.read()

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
    """Aceita HH:MM:SS.mmm, MM:SS.mmm, SS.mmm, virgula decimal ou numero puro."""
    if isinstance(tc, (int, float)):
        return float(tc)
    partes = str(tc).strip().replace(",", ".").split(":")
    if not 1 <= len(partes) <= 3:
        raise ValueError(f"timecode invalido: {tc!r}")
    total = 0.0
    for p in partes:
        total = total * 60 + float(p)
    return total


def segundos_para_srt(seg):
    """Timecode SRT em milissegundos inteiros (59.9996 -> 00:01:00,000)."""
    ms = max(0, round(seg * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def corte_valido(corte, duracao_video):
    try:
        ini = timecode_para_segundos(corte.get("inicio"))
        fim = timecode_para_segundos(corte.get("fim"))
    except (ValueError, TypeError, AttributeError):
        return None
    fim = min(fim, duracao_video) if duracao_video else fim
    if ini < 0 or not 5 <= fim - ini <= 180:
        return None
    return ini, fim

def identificar_melhores_momentos(blocos):
    amostra_srt = ""
    for b in blocos:
        amostra_srt += f"[{b['in']} -> {b['out']}] {b['txt']}\n"
    amostra_srt = amostra_srt[:14000]

    prompt = f"""Voce e um especialista em marketing de conteudo. Analise a transcricao e selecione os 3 trechos mais impactantes para video curto (entre 25 e 60 segundos).
Retorne OBRIGATORIAMENTE um JSON com a chave "cortes":
{{
  "cortes": [
    {{
      "titulo": "Titulo chamativo sem acentos",
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
        return []

def extrair_srt_parcial(caminho_srt_orig, start_sec, end_sec, caminho_srt_dest):
    blocos = srt_para_texto(caminho_srt_orig)
    idx = 1
    with open(caminho_srt_dest, "w", encoding="utf-8") as f:
        for b in blocos:
            s_in = timecode_para_segundos(b["in"])
            s_out = timecode_para_segundos(b["out"])
            if s_out >= start_sec and s_in <= end_sec:
                rel_in = max(0.0, s_in - start_sec)
                rel_out = min(end_sec - start_sec, s_out - start_sec)
                
                tc1 = segundos_para_srt(rel_in)
                tc2 = segundos_para_srt(rel_out)
                f.write(f"{idx}\n{tc1} --> {tc2}\n{b['txt']}\n\n")
                idx += 1

def renderizar_corte_vertical(video_orig, start_sec, end_sec, srt_corte, video_saida):
    duracao = end_sec - start_sec
    if duracao <= 5:
        return

    # O ffmpeg roda dentro da pasta do corte e recebe so o nome do .srt:
    # evita escapar "C:", apostrofos e colchetes dentro do filtro.
    srt_escapado = os.path.basename(srt_corte)
    # Margem inferior adaptada para 9:16 (MarginV = 80px)
    estilo = "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H60000000,BorderStyle=1,Outline=1,Shadow=1,Alignment=2,MarginV=80"

    filtro_complexo = (
        f"[0:v]split=2[bg_in][fg_in];"
        f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:6[bg];"
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
        os.path.abspath(video_saida)
    ]
    res = subprocess.run(cmd, cwd=os.path.dirname(os.path.abspath(srt_corte)))
    if res.returncode != 0:
        print(f"    [ERRO] ffmpeg falhou ao renderizar {os.path.basename(video_saida)}")

def processar_cortes(dir_saida):
    pasta_cortes = os.path.join(dir_saida, "Cortes_9x16")
    os.makedirs(pasta_cortes, exist_ok=True)

    pasta_legendas = os.path.join(dir_saida, "1_Legendas")
    if not os.path.exists(pasta_legendas):
        return

    # Cada video com a SUA legenda (antes: primeiro .mp4 + primeiro .srt, de aulas diferentes)
    for srt_nome in sorted(f for f in os.listdir(pasta_legendas) if f.endswith(".srt")):
        nome = os.path.splitext(srt_nome)[0]
        candidatos = [os.path.join(dir_saida, f"{nome}_DINAMICO.mp4"), os.path.join(dir_saida, f"{nome}.mp4")]
        video_alvo = next((c for c in candidatos if os.path.exists(c)), None)
        if video_alvo:
            processar_corte_video(video_alvo, os.path.join(pasta_legendas, srt_nome), pasta_cortes)


def duracao_video(caminho):
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", caminho],
                         capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def processar_corte_video(video_alvo, srt_principal, pasta_cortes):
    nome_video = os.path.splitext(os.path.basename(video_alvo))[0]
    blocos = srt_para_texto(srt_principal)
    if not blocos:
        return

    print("    [IA] Llama selecionando os melhores momentos...")
    melhores = identificar_melhores_momentos(blocos)
    if not melhores:
        melhores = [{"titulo": "Corte_Principal", "inicio": blocos[0]["in"], "fim": blocos[min(len(blocos)-1, 15)]["out"]}]

    dur = duracao_video(video_alvo)
    validos = [(c, corte_valido(c, dur)) for c in melhores]
    validos = [(c, t) for c, t in validos if t]
    if not validos:
        print("    [AVISO] IA nao sugeriu cortes validos; usando o inicio da aula.")
        validos = [({"titulo": "Corte_Principal"}, (0.0, min(dur or 45.0, 45.0)))]

    for i, (corte, (s_in, s_out)) in enumerate(validos, start=1):
        titulo_limpo = re.sub(r"[^\w\s-]", "", str(corte.get("titulo") or f"Corte_{i}")).strip().replace(" ", "_")
        
        nome_corte = f"{nome_video}_Corte_{i}_{titulo_limpo[:60]}.mp4"
        caminho_final_corte = os.path.join(pasta_cortes, nome_corte)
        caminho_srt_temp = os.path.join(pasta_cortes, f"temp_{i}.srt")

        extrair_srt_parcial(srt_principal, s_in, s_out, caminho_srt_temp)
        renderizar_corte_vertical(video_alvo, s_in, s_out, caminho_srt_temp, caminho_final_corte)

        if os.path.exists(caminho_srt_temp):
            os.remove(caminho_srt_temp)

    print(f"    [SUCESSO] Cortes virais 9:16 gerados em: {pasta_cortes}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_cortes(sys.argv[1])
