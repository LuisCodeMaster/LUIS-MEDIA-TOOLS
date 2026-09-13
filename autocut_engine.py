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

def detectar_silencios(caminho_video, db="-32dB", duracao_minima=1.2):
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
        match_inicio = padrao_inicio.search(linha)
        if match_inicio:
            inicio_atual = float(match_inicio.group(1))

        match_fim = padrao_fim.search(linha)
        if match_fim and inicio_atual is not None:
            fim_atual = float(match_fim.group(1))
            silencios.append((inicio_atual, fim_atual))
            inicio_atual = None

    # Obter duracao total do video
    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", caminho_video]
    dur_res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
    duracao_total = float(dur_res.stdout.strip()) if dur_res.stdout.strip() else 0.0

    # Inverter: converter intervalos de silencio em intervalos de voz (fala)
    # Deixamos uma margem de segurança de 0.15s antes e depois para nao cortar palavras
    margem = 0.15
    fala = []
    ponto_atual = 0.0

    for s_inicio, s_fim in silencios:
        corte_fim = max(0.0, s_inicio + margem)
        if corte_fim > ponto_atual:
            fala.append((ponto_atual, corte_fim))
        ponto_atual = min(duracao_total, s_fim - margem)

    if ponto_atual < duracao_total:
        fala.append((ponto_atual, duracao_total))

    return fala, duracao_total

def exportar_edl(tramos_fala, arquivo_edl, nome_clip="CLIP"):
    with open(arquivo_edl, "w", encoding="utf-8") as f:
        f.write("TITLE: AUTOCUT TIMELINE\nFCM: NON-DROP FRAME\n\n")
        relogio_timeline = 0.0
        idx = 1
        for inicio, fim in tramos_fala:
            duracao_bloco = fim - inicio
            tc_src_in  = segundos_para_timecode(inicio)
            tc_src_out = segundos_para_timecode(fim)
            tc_rec_in  = segundos_para_timecode(relogio_timeline)
            tc_rec_out = segundos_para_timecode(relogio_timeline + duracao_bloco)
            relogio_timeline += duracao_bloco

            f.write(f"{idx:03d}  AX       AA/V  C        {tc_src_in} {tc_src_out} {tc_rec_in} {tc_rec_out}\n")
            f.write(f"* FROM CLIP NAME: {nome_clip}\n\n")
            idx += 1

def renderizar_video_cortado(caminho_video, tramos_fala, video_saida):
    if not tramos_fala:
        return
    filtros = []
    concat_args = []
    for i, (inicio, fim) in enumerate(tramos_fala):
        filtros.append(f"[0:v]trim=start={inicio:.3f}:end={fim:.3f},setpts=PTS-STARTPTS[v{i}];")
        filtros.append(f"[0:a]atrim=start={inicio:.3f}:end={fim:.3f},asetpts=PTS-STARTPTS[a{i}];")
        concat_args.append(f"[v{i}][a{i}]")

    filtro_complexo = "".join(filtros) + "".join(concat_args) + f"concat=n={len(tramos_fala)}:v=1:a=1[outv][outa]"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", caminho_video,
        "-filter_complex", filtro_complexo,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        video_saida
    ]
    subprocess.run(cmd)

def processar(caminho_video, pasta_saida):
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    print(f"    Detectando pausas e momentos mortos em: {nome_base}...")
    fala, dur_total = detectar_silencios(caminho_video)

    tempo_economizado = dur_total - sum(f - i for i, f in fala)
    print(f"    [ECONOMIA] {tempo_economizado:.1f} segundos de silencio detectados!")

    # 1. Gera EDL para Premiere / DaVinci
    arquivo_edl = os.path.join(pasta_saida, f"{nome_base}_timeline_cortes.edl")
    exportar_edl(fala, arquivo_edl, nome_clip=os.path.basename(caminho_video))
    print(f"    [EDL] Timeline para DaVinci/Premiere salva: {os.path.basename(arquivo_edl)}")

    # 2. Opcional: renderizar video pronto fatiado
    video_cortado = os.path.join(pasta_saida, f"{nome_base}_sem_silencio.mp4")
    print(f"    [RENDER] Renderizando video fatiado com cortes fluidos...")
    renderizar_video_cortado(caminho_video, fala, video_cortado)
    print(f"    [OK] Video fatiado gerado: {os.path.basename(video_cortado)}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        processar(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        processar(sys.argv[1], os.path.dirname(sys.argv[1]))
