import sys
import os
import re
import subprocess
import shutil

def segundos_para_timecode(segundos, fps=30):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    quadros = int((segundos - int(segundos)) * fps)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}:{quadros:02d}"

def detectar_silencios(caminho_audio, db="-32dB", duracao_minima=1.1, ignorar_silencio_longo=False, limite_silencio=2.5):
    cmd = [
        "ffmpeg", "-hide_banner",
        "-i", caminho_audio,
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

    cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", caminho_audio]
    dur_res = subprocess.run(cmd_dur, stdout=subprocess.PIPE, text=True)
    try:
        duracao_total = float(dur_res.stdout.strip())
    except ValueError:
        duracao_total = 0.0

    if ignorar_silencio_longo:
        silencios_ignorados = [s for s in silencios if (s[1] - s[0]) >= limite_silencio]
        silencios = [s for s in silencios if (s[1] - s[0]) < limite_silencio]
        if silencios_ignorados:
            print(f"    [REGRA DINÂMICA] {len(silencios_ignorados)} pausa(s) >= {limite_silencio}s preservada(s)!")

    margem = 0.25
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

    dir_temp = os.path.dirname(video_saida)
    pasta_chunks = os.path.join(dir_temp, "chunks_temp")
    if os.path.exists(pasta_chunks):
        shutil.rmtree(pasta_chunks)
    os.makedirs(pasta_chunks, exist_ok=True)

    lista_chunks_path = os.path.join(pasta_chunks, "lista_fatias.txt")
    arquivos_fatias = []

    # 1. Fatiar cada trecho de fala individualmente com áudio perfeitamente reamostrado
    for i, (inicio, fim) in enumerate(tramos_fala):
        duracao = fim - inicio
        if duracao < 0.1:
            continue
        chunk_path = os.path.join(pasta_chunks, f"chunk_{i:04d}.mp4")
        
        cmd_chunk = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{inicio:.3f}",
            "-i", caminho_video,
            "-t", f"{duracao:.3f}",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-ar", "48000",
            "-avoid_negative_ts", "make_zero",
            chunk_path
        ]
        res = subprocess.run(cmd_chunk)
        if res.returncode != 0:
            print(f"    [ERRO] ffmpeg falhou no trecho {i} ({inicio:.1f}s)")
            continue
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
            arquivos_fatias.append(chunk_path)

    if not arquivos_fatias:
        return

    # 2. Escreve o arquivo de manifesto para o demuxer do FFmpeg
    with open(lista_chunks_path, "w", encoding="utf-8") as f:
        for arq in arquivos_fatias:
            caminho_absoluto = os.path.abspath(arq).replace("\\", "/")
            f.write(f"file '{caminho_absoluto}'\n")

    # 3. Concatenação segura sem perda de áudio
    cmd_concat = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0",
        "-i", lista_chunks_path,
        "-c", "copy",
        video_saida
    ]
    res = subprocess.run(cmd_concat)
    if res.returncode != 0:
        print("    [ERRO] ffmpeg falhou ao juntar os trechos")
        if os.path.exists(video_saida):
            os.remove(video_saida)  # nunca deixar video pela metade com cara de pronto

    try:
        shutil.rmtree(pasta_chunks)
    except OSError:
        pass

def processar(caminho_video, pasta_saida_video, pasta_saida_edl=None, ignorar_silencio_longo=False, limite_silencio=2.5):
    if not pasta_saida_edl:
        pasta_saida_edl = pasta_saida_video
        
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    print(f"    Detectando pausas em: {nome_base}...")
    
    audio_temp = os.path.join(pasta_saida_video, f"temp_detect_{nome_base}.wav")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", caminho_video, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_temp])

    fala, dur_total = detectar_silencios(audio_temp, ignorar_silencio_longo=ignorar_silencio_longo, limite_silencio=limite_silencio)
    if os.path.exists(audio_temp):
        os.remove(audio_temp)

    if not fala:
        print("    [AVISO] Nenhum trecho valido encontrado. Copiando original.")
        shutil.copy(caminho_video, os.path.join(pasta_saida_video, f"{nome_base}_DINAMICO.mp4"))
        return

    tempo_economizado = dur_total - sum(f - i for i, f in fala)
    print(f"    [CORTE] {tempo_economizado:.1f}s de silencio eliminados.")

    # 1. Timeline EDL
    arquivo_edl = os.path.join(pasta_saida_edl, f"{nome_base}_timeline_cortes.edl")
    exportar_edl(fala, arquivo_edl, nome_clip=os.path.basename(caminho_video))

    # 2. Renderização blindada via Demuxer Concat
    video_cortado = os.path.join(pasta_saida_video, f"{nome_base}_DINAMICO.mp4")
    print(f"    [RENDER] Renderizando video fatiado com metodo demuxer blindado (som garantido)...")
    renderizar_video_cortado(caminho_video, fala, video_cortado)
    print(f"    [OK] Video dinamico gerado: {os.path.basename(video_cortado)}")
    return video_cortado

if __name__ == "__main__":
    limite = 2.5
    ignorar = "--ignorar-4s" in sys.argv or "--limite" in sys.argv
    
    if "--limite" in sys.argv:
        idx = sys.argv.index("--limite")
        try:
            limite = float(sys.argv[idx + 1])
            ignorar = True
        except:
            limite = 2.5

    args = [a for i, a in enumerate(sys.argv[1:]) if a not in ["--ignorar-4s", "--limite"] and (i == 0 or sys.argv[i] != "--limite")]
    if len(args) > 1:
        processar(args[0], args[1], ignorar_silencio_longo=ignorar, limite_silencio=limite)
    elif len(args) == 1:
        processar(args[0], os.path.dirname(args[0]), ignorar_silencio_longo=ignorar, limite_silencio=limite)