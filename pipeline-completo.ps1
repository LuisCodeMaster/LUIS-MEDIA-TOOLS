param(
    [string]$Aula = "Aula1"
)

$ErrorActionPreference = "Stop"

$raiz = (Get-Location).Path
$dirEntrada = Join-Path $raiz "entrada\$Aula"
$dirSaida   = Join-Path $raiz "saida\$Aula"

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

$videos = Get-ChildItem -Path $dirEntrada -Filter "*.mp4" | Sort-Object Name

if ($videos.Count -eq 0) {
    Write-Host "[AVISO] Nenhum video .mp4 encontrado em $dirEntrada" -ForegroundColor Yellow
    exit 0
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: PROCESSAMENTO INCREMENTAL ($Aula)   " -ForegroundColor Cyan
Write-Host "   Total de videos detectados: $($videos.Count)          " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    $legendaFinal = Join-Path $pastas["1"] "$nome.srt"
    $audioBrutoFinal = Join-Path $pastas["2"] "$nome.wav"

    # TRAVA DE CACHE: Se já foi processado, pula
    if ((Test-Path $legendaFinal) -and (Test-Path $audioBrutoFinal)) {
        Write-Host "[CACHE HIT] $nome ja possui legenda e audio bruto. Pulando..." -ForegroundColor DarkGray
        continue
    }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # 1. Extrair audio bruto
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        ffmpeg -y -i $video.FullName -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp 2>$null
    }

    # 2. Whisper (transcricao e legendas)
    $srtTemp = Join-Path $dirTempChunk "$nome.srt"
    if (-not (Test-Path $srtTemp)) {
        Write-Host "    Transcrevendo com Whisper..." -ForegroundColor Yellow
        whisper $audioBrutoTemp --model medium --language pt --output_dir $dirTempChunk 2>$null
    }

    # Copia arquivos processados para as pastas definitivas
    if (Test-Path $srtTemp) {
        Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force
    }
    if (Test-Path $audioBrutoTemp) {
        Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force
    }
}

# 3. Extrair slides caso 4_Slides_Extraidos esteja vazia
$slidesExistentes = (Get-ChildItem -Path $pastas["4"] -Include "*.jpg","*.png" -Recurse -ErrorAction SilentlyContinue).Count
if ($slidesExistentes -eq 0) {
    Write-Host "`n>>> [SLIDES] Extraindo frames de referencia..." -ForegroundColor Cyan
    foreach ($video in $videos) {
        $slideDestino = Join-Path $pastas["4"] "$($video.BaseName)-slide.jpg"
        ffmpeg -y -ss 00:00:05 -i $video.FullName -vframes 1 -q:v 2 $slideDestino 2>$null
    }
}

# 4. Processamento Editorial e Apostila (se houver o script)
if (Test-Path (Join-Path $raiz "editorial_engine.py")) {
    Write-Host "`n>>> [EDITORIAL] Gerando apostila ilustrada e analise..." -ForegroundColor Cyan
    python (Join-Path $raiz "editorial_engine.py") $dirSaida
    $apostila = Join-Path $pastas["6"] "apostila-ilustrada.html"
    if (Test-Path $apostila) {
        Copy-Item -Path $apostila -Destination $pastas["5"] -Force
    }
}

# 5. Limpeza de subpastas intermediárias temporárias
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$Aula-\d+" } | Remove-Item -Recurse -Force

# 6. Gerar pacote compactado final
Write-Host "`n>>> [EMPACOTAMENTO] Gerando arquivo compactado entregavel..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$Aula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"] -DestinationPath $arquivoZip -Force

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "   PIPELINE FINALIZADO COM SUCESSO!                     " -ForegroundColor Green
Write-Host "   Entregavel: $arquivoZip                              " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
