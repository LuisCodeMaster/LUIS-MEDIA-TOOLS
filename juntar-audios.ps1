$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

if (-not (Test-Path $PastaSaida)) {
    New-Item -ItemType Directory -Path $PastaSaida -Force | Out-Null
}

$exts = @(".mp4", ".mkv", ".mov", ".avi", ".webm", ".wav", ".mp3")
$arquivos = Get-ChildItem -Path $PastaEntrada -File | Where-Object { $exts -contains $_.Extension.ToLower() }

if ($null -eq $arquivos -or $arquivos.Count -eq 0) {
    Write-Host "Nenhum arquivo de video ou audio encontrado na pasta: $PastaEntrada" -ForegroundColor Yellow
    exit 0
}

# Ordenacao natural (garante que Aula1-2 venha antes de Aula1-10)
$arquivosOrdenados = $arquivos | Sort-Object { [regex]::Replace($_.Name, '\d+', { $args[0].Value.PadLeft(6, '0') }) }

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "       JUNÇÃO DE ÁUDIOS — LUIS MEDIA TOOLS     " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "Arquivos identificados na ordem:" -ForegroundColor DarkGray
foreach ($arq in $arquivosOrdenados) {
    Write-Host "  -> $($arq.Name)" -ForegroundColor White
}
Write-Host "-----------------------------------------------" -ForegroundColor Cyan

# 1. Gera audio intermediario padronizado (16kHz PCM WAV) para cada video
$tempDir = Join-Path $PastaSaida "_temp_concat"
if (Test-Path $tempDir) { Remove-Item -Path $tempDir -Recurse -Force }
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

$concatListPath = Join-Path $tempDir "lista.txt"
$linhasLista = @()

$index = 1
$total = $arquivosOrdenados.Count

foreach ($item in $arquivosOrdenados) {
    $pct = [int]((($index - 1) / $total) * 100)
    Write-Progress -Activity "Extraindo áudios para junção" -Status "Processando [$index/$total]: $($item.Name)" -PercentComplete $pct

    $tempWav = Join-Path $tempDir ("parte_{0:D4}.wav" -f $index)
    & ffmpeg -y -i $item.FullName -vn -acodec pcm_s16le -ar 48000 -ac 2 "$tempWav" -loglevel error

    # Caminho com barras normais para a lista do FFmpeg concat
    $caminhoFormatado = $tempWav.Replace('\', '/')
    $linhasLista += "file '$caminhoFormatado'"
    $index++
}

[System.IO.File]::WriteAllLines($concatListPath, [string[]]$linhasLista, [System.Text.UTF8Encoding]::new($false))

Write-Progress -Activity "Juntando áudios contínuos" -Status "Concatenando em arquivo único..." -PercentComplete 90

$SaidaWav = Join-Path $PastaSaida "aula-completa.wav"
$SaidaMp3 = Join-Path $PastaSaida "aula-completa.mp3"

Write-Host "Unificando faixas em um arquivo mestre..." -ForegroundColor Yellow

# Concatena em PCM WAV de alta qualidade (ideal para Premiere/DaVinci)
& ffmpeg -y -f concat -safe 0 -i "$concatListPath" -c copy "$SaidaWav" -loglevel error

# Gera tambem versao comprimida MP3 para audicao rapida
& ffmpeg -y -i "$SaidaWav" -c:a libmp3lame -q:a 2 "$SaidaMp3" -loglevel error

# Limpeza de temporarios
Remove-Item -Path $tempDir -Recurse -Force
Write-Progress -Activity "Extraindo áudios para junção" -Completed

Write-Host ""
Write-Host "===============================================" -ForegroundColor Green
Write-Host "        ÁUDIO UNIFICADO COM SUCESSO!           " -ForegroundColor Green
Write-Host "===============================================" -ForegroundColor Green
Write-Host "Arquivo Master WAV (Edição) : $SaidaWav" -ForegroundColor Cyan
Write-Host "Arquivo Compacto MP3 (Estudo): $SaidaMp3" -ForegroundColor Cyan
Write-Host ""
[System.Console]::Beep(1000, 200)
[System.Console]::Beep(1200, 300)