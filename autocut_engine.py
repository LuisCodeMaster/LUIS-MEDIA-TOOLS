import sys
import os
import re
import subprocess

def segundos_para_timecode(segundos, fps=30):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    quadros = int((segundos - int(segundos)) * fps)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}:{quadros:02d}"

def detectar_silencios(caminho_video, db="-32dB", duracao_minima=1.1):
    cmd = [
        "ffmpeg", "-hide_banner",
        "-i", caminho_video,
        "-af", f"silencedetect=noise={db}:d={duracao_minima}",
        "-f", "null", "-"
    ]
    resultado = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    saida = resultado.stderr

    padrao_inicio = re.compile(r"silence_start: (\d+(?:\.\d+)?)")
    padrao_fim = re.compile(r"silence_end: (\d+(?:\.\d+)?)")

    silencios = []
    inicio_atual = None

    for linha in saida.splitlines():
        m_in = padrao_inicio.search(linha)
        if m_in:
            inicio_atual = float(m_in.group(1))
        m_fim = padrao_fim.search(linha)
        if m_fim and inicio_atual is not None:
            silencios.append((inicio_atual, float(m_fim.group(1))))
            inicio_atual = None

    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", caminho_video]
    dur_res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
    duracao_total = float(dur_res.stdout.strip()) if dur_res.stdout.strip() else 0.0

    # Margem suave de 0.12s para garantir o ataque e relaxamento natural das palavras
    margem = 0.12
    fala = []
    ponto_atual = 0.0

    for s_in, s_fim in silencios:
        corte_fim = max(0.0, s_in + margem)
        if corte_fim > ponto_atual:
            fala.append((ponto_atual, corte_fim))
        ponto_atual = min(duracao_total, s_fim - margem)

    if ponto_atual < duracao_total:
        fala.append((ponto_atual, duracao_total))

    return fala, duracao_total

def exportar_edl(tramos_fala, arquivo_edl, nome_clip="CLIP"):
    with open(arquivo_edl, "w", encoding="utf-8") as f:
        f.write("TITLE: AUTOCUT TIMELINE\nFCM: NON-DROP FRAME\n\n")
        relogio = 0.0
        idx = 1
        for inicio, fim in tramos_fala:
            duracao = fim - inicio
            tc_s_in, tc_s_out = segundos_para_timecode(inicio), segundos_para_timecode(fim)
            tc_r_in, tc_r_out = segundos_para_timecode(relogio), segundos_para_timecode(relogio + duracao)
            relogio += duracao
            f.write(f"{idx:03d}  AX       AA/V  C        {tc_s_in} {tc_s_out} {tc_r_in} {tc_r_out}\n")
            f.write(f"* FROM CLIP NAME: {nome_clip}\n\n")
            idx += 1

def renderizar_video_cortado(caminho_video, tramos_fala, video_saida):
    if not tramos_fala:
        return
    filtros = []
    concat_args = []
    for i, (inicio, fim) in enumerate(tramos_fala):
        # afade suave nos tramos para evitar estalos eletroacústicos
        filtros.append(f"[0:v]trim=start={inicio:.3f}:end={fim:.3f},setpts=PTS-STARTPTS[v{i}];")
        filtros.append(f"[0:a]atrim=start={inicio:.3f}:end={fim:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.015,afade=t=out:d=0.015[a{i}];")
        concat_args.append(f"[v{i}][a{i}]")

    filtro_complexo = "".join(filtros) + "".join(concat_args) + f"concat=n={len(tramos_fala)}:v=1:a=1[outv][outa]"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", caminho_video,
        "-filter_complex", filtro_complexo,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "faster", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        video_saida
    ]
    subprocess.run(cmd)

def processar(caminho_video, pasta_saida_video, pasta_saida_edl=None):
    if not pasta_saida_edl:
        pasta_saida_edl = pasta_saida_video
        
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    print(f"    Detectando pausas de respiracao em: {nome_base}...")
    fala, dur_total = detectar_silencios(caminho_video)

    tempo_economizado = dur_total - sum(f - i for i, f in fala)
    print(f"    [CORTE] {tempo_economizado:.1f}s removidos (ritmo acelerado)")

    # 1. Timeline EDL
    arquivo_edl = os.path.join(pasta_saida_edl, f"{nome_base}_timeline_cortes.edl")
    exportar_edl(fala, arquivo_edl, nome_clip=os.path.basename(caminho_video))

    # 2. Renderização do vídeo dinâmico com micro-fade
    video_cortado = os.path.join(pasta_saida_video, f"{nome_base}_DINAMICO.mp4")
    print(f"    [RENDER] Gerando video fluido com transicao anti-estalo...")
    renderizar_video_cortado(caminho_video, fala, video_cortado)
    print(f"    [OK] Video dinamico gerado: {os.path.basename(video_cortado)}")
    return video_cortado

if __name__ == "__main__":
    if len(sys.argv) > 2:
        processar(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        processar(sys.argv[1], os.path.dirname(sys.argv[1]))
