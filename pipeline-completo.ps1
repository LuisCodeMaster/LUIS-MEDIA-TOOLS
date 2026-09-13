param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"

# 1. Identificar origem e nome do projeto
if ($CaminhoPasta -ne "") {
    $itemAlvo = Get-Item -LiteralPath $CaminhoPasta
    if ($itemAlvo.PSIsContainer) {
        $dirEntrada = $itemAlvo.FullName
        $nomeAula   = $itemAlvo.Name
    } else {
        $dirEntrada = $itemAlvo.DirectoryName
        $nomeAula   = (Get-Item $dirEntrada).Name
    }
} else {
    if ($Aula -eq "") { $Aula = "Aula1" }
    $nomeAula   = $Aula
    $dirEntrada = Join-Path $raiz "entrada\$nomeAula"
}

if (-not (Test-Path $dirEntrada)) {
    Write-Error "[ERRO] Pasta de entrada nao encontrada: $dirEntrada"
    exit 1
}

# 2. Janela Grafica para Selecionar Destino Definitivo
$saidaPadrao = Join-Path $raiz "saida\$nomeAula"

if ($PastaDestino -eq "") {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Selecione a pasta de destino final para consolidar o projeto [$nomeAula]:"
    $dialog.SelectedPath = (Join-Path $raiz "saida")
    $dialog.ShowNewFolderButton = $true

    $resultado = $dialog.ShowDialog()

    if ($resultado -eq [System.Windows.Forms.DialogResult]::OK -and (-not [string]::IsNullOrWhiteSpace($dialog.SelectedPath))) {
        if ($dialog.SelectedPath -match "saida$") {
            $dirSaida = Join-Path $dialog.SelectedPath $nomeAula
        } else {
            $dirSaida = $dialog.SelectedPath
        }
    } else {
        Write-Host "[INFO] Usando diretorio padrao: $saidaPadrao" -ForegroundColor Gray
        $dirSaida = $saidaPadrao
    }
} else {
    $dirSaida = $PastaDestino
}

if (-not (Test-Path $dirSaida)) {
    New-Item -ItemType Directory -Path $dirSaida -Force | Out-Null
}

# 3. Estrutura temporaria de entregaveis (pastas 1 a 7)
$pastas = @{
    "1" = Join-Path $dirSaida "1_Legendas"
    "2" = Join-Path $dirSaida "2_Audio_Bruto"
    "3" = Join-Path $dirSaida "3_Audio_Tratado"
    "4" = Join-Path $dirSaida "4_Slides_Extraidos"
    "5" = Join-Path $dirSaida "5_Editorial"
    "6" = Join-Path $dirSaida "6_Documentos"
    "7" = Join-Path $dirSaida "7_Cortes_Timeline"
}

foreach ($p in $pastas.Values) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# 4. Varredura de vídeos (ignora os videos ja fatiados _sem_silencio)
$videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "_sem_silencio" } | Sort-Object Name

if ($videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirSaida -Include "*.mp4","*.mkv","*.mov" | Where-Object { $_.Name -notmatch "_sem_silencio" } | Sort-Object Name
    if ($videos.Count -eq 0) {
        Write-Host "[AVISO] Nenhum video compativel encontrado em $dirEntrada ou $dirSaida" -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: PIPELINE MASTER AUTOCUT + LLAMA     " -ForegroundColor Cyan
Write-Host "   Projeto: $nomeAula                                    " -ForegroundColor Cyan
Write-Host "   Origem:  $dirEntrada                                  " -ForegroundColor Cyan
Write-Host "   Destino: $dirSaida                                    " -ForegroundColor Cyan
Write-Host "   Videos:  $($videos.Count)                             " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# 5. Minutagem acumulada para YouTube/Vimeo
$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    # Calculo de duracao via ffprobe
    $duracaoStr = (& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $video.FullName)
    $duracao = 0.0
    [double]::TryParse($duracaoStr, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$duracao) | Out-Null

    $horas = [math]::Floor($tempoAcumulado / 3600)
    $minutos = [math]::Floor(($tempoAcumulado % 3600) / 60)
    $segundos = [math]::Floor($tempoAcumulado % 60)
    $stamp = if ($horas -gt 0) { "{0:D2}:{1:D2}:{2:D2}" -f [int]$horas, [int]$minutos, [int]$segundos } else { "{0:D2}:{1:D2}" -f [int]$minutos, [int]$segundos }
    $listaCapitulos += "$stamp - $nome"
    $tempoAcumulado += $duracao

    $legendaFinal    = Join-Path $pastas["1"] "$nome.srt"
    $audioBrutoFinal = Join-Path $pastas["2"] "$nome.wav"
    $audioTratFinal  = Join-Path $pastas["3"] "$nome.wav"

    # Trava de Cache
    if ((Test-Path $legendaFinal) -and (Test-Path $audioBrutoFinal) -and (Test-Path $audioTratFinal)) {
        Write-Host "[CACHE HIT] $nome ja processado. Pulando..." -ForegroundColor DarkGray
        continue
    }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # 1. Extração de Audio Bruto (16kHz mono)
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        & ffmpeg -hide_banner -loglevel error -y -i $video.FullName -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp
    }

    # 2. Tratamento Broadcast EBU R128 + Highpass 80Hz
    $audioTratTemp = Join-Path $dirTempChunk "$($nome)_tratado.wav"
    if (-not (Test-Path $audioTratTemp)) {
        Write-Host "    Tratando audio (Filtros EBU R128 + Limpeza)..." -ForegroundColor DarkCyan
        & ffmpeg -hide_banner -loglevel error -y -i $audioBrutoTemp -af "highpass=f=80,loudnorm=I=-16:LRA=11:TP=-1.5" $audioTratTemp
    }

    # 3. Transcricao via faster-whisper (Ryzen CPU / int8)
    $srtTemp = Join-Path $dirTempChunk "$nome.srt"
    if (-not (Test-Path $srtTemp)) {
        Write-Host "    Transcrevendo com Whisper..." -ForegroundColor Yellow
        $scriptTranscricao = @"
import os, sys
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
try:
    from faster_whisper import WhisperModel
    model = WhisperModel('medium', device='cpu', compute_type='int8')
    segments, _ = model.transcribe(r'$audioBrutoTemp', language='pt')
    with open(r'$srtTemp', 'w', encoding='utf-8') as f:
        idx = 1
        for s in segments:
            h1, m1, s1 = int(s.start // 3600), int((s.start % 3600) // 60), s.start % 60
            h2, m2, s2 = int(s.end // 3600), int((s.end % 3600) // 60), s.end % 60
            f.write(f'{idx}\n{h1:02d}:{m1:02d}:{s1:06.3f}'.replace('.', ',') + ' --> ' + f'{h2:02d}:{m2:02d}:{s2:06.3f}'.replace('.', ',') + f'\n{s.text.strip()}\n\n')
            idx += 1
except Exception:
    import subprocess
    subprocess.run(['whisper', r'$audioBrutoTemp', '--model', 'medium', '--language', 'pt', '--output_dir', r'$dirTempChunk'])
"@
        python -c $scriptTranscricao
    }

    # 4. Auto-Cut de Silêncio e Timeline EDL
    if (Test-Path (Join-Path $raiz "autocut_engine.py")) {
        Write-Host "    Detectando silencios e gerando EDL..." -ForegroundColor DarkYellow
        & python (Join-Path $raiz "autocut_engine.py") $video.FullName $pastas["7"]
    }

    # Copia para as pastas consolidadas
    if (Test-Path $srtTemp) { Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force }
    if (Test-Path $audioBrutoTemp) { Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force }
    if (Test-Path $audioTratTemp) { Copy-Item -Path $audioTratTemp -Destination $pastas["3"] -Force }
}

# Salva minutagem
$listaCapitulos | Out-File -FilePath $minutagemArquivo -Encoding UTF8
Write-Host "[OK] Minutagem gerada em: $minutagemArquivo" -ForegroundColor Cyan

# 6. Slides Inteligentes (Scene Detection)
$slidesCount = (Get-ChildItem -Path $pastas["4"] -Include "*.jpg","*.png" -Recurse -ErrorAction SilentlyContinue).Count
if ($slidesCount -eq 0) {
    Write-Host "`n>>> [SLIDES] Detectando trocas reais de slides com FFmpeg..." -ForegroundColor Cyan
    foreach ($video in $videos) {
        $prefixo = $video.BaseName
        $padraoSaida = Join-Path $pastas["4"] "${prefixo}_slide_%03d.jpg"
        
        & ffmpeg -hide_banner -loglevel error -y -i $video.FullName `
            -vf "select='gt(scene,0.25)',mpdecimate" `
            -vsync vfr -q:v 2 $padraoSaida
            
        $gerados = Get-ChildItem -Path $pastas["4"] -Filter "${prefixo}_slide_*.jpg"
        if ($gerados.Count -eq 0) {
            $slideFallback = Join-Path $pastas["4"] "${prefixo}_slide_001.jpg"
            & ffmpeg -hide_banner -loglevel error -y -ss 00:00:05 -i $video.FullName -vframes 1 -q:v 2 $slideFallback
        } else {
            Write-Host "    [OK] $($gerados.Count) slide(s) extraido(s) de $prefixo" -ForegroundColor DarkCyan
        }
    }
}

# 7. Motor Editorial e PDF da Apostila
if (Test-Path (Join-Path $raiz "editorial_engine.py")) {
    Write-Host "`n>>> [EDITORIAL] Gerando apostila didatica..." -ForegroundColor Cyan
    & python (Join-Path $raiz "editorial_engine.py") $dirSaida
    $apostilaHtml = Join-Path $pastas["6"] "apostila-ilustrada.html"
    if (Test-Path $apostilaHtml) {
        Copy-Item -Path $apostilaHtml -Destination $pastas["5"] -Force
        
        $edgePaths = @(
            "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        )
        $edgeExe = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($edgeExe) {
            $pdfDestino = Join-Path $pastas["6"] "Apostila-Oficial.pdf"
            Write-Host "    Convertendo apostila para PDF..." -ForegroundColor DarkCyan
            & $edgeExe --headless --disable-gpu --print-to-pdf="$pdfDestino" "$apostilaHtml" 2>$null
        }
    }
}

# 8. Chamada da IA Local Llama (Resumo Executivo e Quiz de Fixação)
if (Test-Path (Join-Path $raiz "gerador_ia.py")) {
    Write-Host "`n>>> [IA LOCAL - LLAMA] Criando Resumo Executivo e Quiz..." -ForegroundColor Magenta
    & python (Join-Path $raiz "gerador_ia.py") $dirSaida
}

# 9. Limpeza de subpastas temporarias
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" -or $_.Name -match "^Aula\d+-\d+" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 10. Empacotamento dos entregaveis (pastas 1 a 7)
Write-Host "`n>>> [EMPACOTAMENTO] Gerando entregavel ZIP..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"], $pastas["7"] -DestinationPath $arquivoZip -Force

# 11. Faxina de intermediarios (SSD protegido)
if ((Test-Path $arquivoZip) -and ((Get-Item $arquivoZip).Length -gt 1024)) {
    Write-Host ">>> [LIMPEZA] Removendo pastas soltas intermediarias..." -ForegroundColor DarkGray
    foreach ($p in $pastas.Values) {
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

# 12. Mover videos brutos e fatiados para a raiz do destino
Write-Host "`n>>> [CONSOLIDACAO] Movendo videos para o destino final..." -ForegroundColor Cyan
foreach ($video in $videos) {
    if ($video.DirectoryName -ne $dirSaida) {
        $destinoFinalVideo = Join-Path $dirSaida $video.Name
        Move-Item -LiteralPath $video.FullName -Destination $destinoFinalVideo -Force
        Write-Host "    Movido bruto: $($video.Name)" -ForegroundColor Gray
    }
}

# 13. Faxina da pasta de origem (se ficou vazia)
if ((Test-Path $dirEntrada) -and ($dirEntrada -ne $dirSaida) -and ($dirEntrada -ne $raiz)) {
    $itensRestantes = Get-ChildItem -Path $dirEntrada -Force
    if ($itensRestantes.Count -eq 0) {
        Write-Host ">>> [LIMPEZA ORIGEM] Pasta de origem vazia removida: $dirEntrada" -ForegroundColor DarkGray
        Remove-Item -LiteralPath $dirEntrada -Force -ErrorAction SilentlyContinue
    }
}

# 14. Notificacao Sonora e Alerta Visual
[System.Console]::Beep(1000, 300)
[System.Console]::Beep(1500, 400)
try {
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = "LUIS-MEDIA-TOOLS Completo!"
    $notify.BalloonTipText = "Videos, Auto-Cut EDL, Resumo e Quiz gerados em [$nomeAula]."
    $notify.Visible = $true
    $notify.ShowBalloonTip(4000)
} catch {}

# Abre o destino no Explorer
explorer.exe $dirSaida

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "   PIPELINE FINALIZADO COM SUCESSO!                     " -ForegroundColor Green
Write-Host "   Local Final: $dirSaida                               " -ForegroundColor Green
Write-Host "   Entregavel:  $arquivoZip                             " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
