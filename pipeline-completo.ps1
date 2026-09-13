param(
    [string]$Aula = "",
    [string]$CaminhoPasta = ""
)

$ErrorActionPreference = "Stop"
$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"

# Identifica o caminho de entrada e o nome da aula
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

$dirSaida = Join-Path $raiz "saida\$nomeAula"

if (-not (Test-Path $dirEntrada)) {
    Write-Error "[ERRO] Pasta de entrada nao encontrada: $dirEntrada"
    exit 1
}

# Criar estrutura de entregáveis de 1 a 6
$pastas = @{
    "1" = Join-Path $dirSaida "1_Legendas"
    "2" = Join-Path $dirSaida "2_Audio_Bruto"
    "3" = Join-Path $dirSaida "3_Audio_Tratado"
    "4" = Join-Path $dirSaida "4_Slides_Extraidos"
    "5" = Join-Path $dirSaida "5_Editorial"
    "6" = Join-Path $dirSaida "6_Documentos"
}

foreach ($p in $pastas.Values) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# Detecta múltiplos formatos de vídeo
$videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Sort-Object Name

if ($videos.Count -eq 0) {
    Write-Host "[AVISO] Nenhum video (.mp4, .mkv, .mov) encontrado em $dirEntrada" -ForegroundColor Yellow
    exit 0
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: ARRASTAR E SOLTAR ATIVADO           " -ForegroundColor Cyan
Write-Host "   Projeto: $nomeAula                                    " -ForegroundColor Cyan
Write-Host "   Origem:  $dirEntrada                                  " -ForegroundColor Cyan
Write-Host "   Total de videos: $($videos.Count)                     " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    $legendaFinal    = Join-Path $pastas["1"] "$nome.srt"
    $audioBrutoFinal = Join-Path $pastas["2"] "$nome.wav"

    # TRAVA DE CACHE
    if ((Test-Path $legendaFinal) -and (Test-Path $audioBrutoFinal)) {
        Write-Host "[CACHE HIT] $nome ja processado. Pulando..." -ForegroundColor DarkGray
        continue
    }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # 1. Extrair audio bruto
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        ffmpeg -y -i $video.FullName -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp 2>$null
    }

    # 2. Transcrição Whisper
    $srtTemp = Join-Path $dirTempChunk "$nome.srt"
    if (-not (Test-Path $srtTemp)) {
        Write-Host "    Transcrevendo com Whisper..." -ForegroundColor Yellow
        whisper $audioBrutoTemp --model medium --language pt --output_dir $dirTempChunk 2>$null
    }

    # Distribui para as pastas consolidadas
    if (Test-Path $srtTemp) {
        Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force
    }
    if (Test-Path $audioBrutoTemp) {
        Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force
    }
}

# 3. Slides Automáticos
$slidesCount = (Get-ChildItem -Path $pastas["4"] -Include "*.jpg","*.png" -Recurse -ErrorAction SilentlyContinue).Count
if ($slidesCount -eq 0) {
    Write-Host "`n>>> [SLIDES] Extraindo frames de referencia..." -ForegroundColor Cyan
    foreach ($video in $videos) {
        $slideDestino = Join-Path $pastas["4"] "$($video.BaseName)-slide.jpg"
        ffmpeg -y -ss 00:00:05 -i $video.FullName -vframes 1 -q:v 2 $slideDestino 2>$null
    }
}

# 4. Motor Editorial
if (Test-Path (Join-Path $raiz "editorial_engine.py")) {
    Write-Host "`n>>> [EDITORIAL] Gerando material de apoio..." -ForegroundColor Cyan
    python (Join-Path $raiz "editorial_engine.py") $dirSaida
    $apostila = Join-Path $pastas["6"] "apostila-ilustrada.html"
    if (Test-Path $apostila) {
        Copy-Item -Path $apostila -Destination $pastas["5"] -Force
    }
}

# 5. Limpeza de temporários
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" } | Remove-Item -Recurse -Force

# 6. Empacotamento
Write-Host "`n>>> [EMPACOTAMENTO] Gerando entregavel..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"] -DestinationPath $arquivoZip -Force

# 7. Abre a pasta pronta na tela
explorer.exe $dirSaida

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "   PIPELINE FINALIZADO COM SUCESSO!                     " -ForegroundColor Green
Write-Host "   Entregavel: $arquivoZip                              " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
