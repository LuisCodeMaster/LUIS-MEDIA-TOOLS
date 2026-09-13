param(
    [Parameter(Mandatory=$false)]
    [string]$Arquivo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

# Parametros EBU R128 / YouTube (-14 LUFS)
$FiltroLoudnorm = "loudnorm=I=-14:TP=-1.5:LRA=11"

function Normalizar-Arquivo {
    param(
        [string]$CaminhoArquivo,
        [int]$Atual = 1,
        [int]$Total = 1
    )

    $ArquivoFull = (Resolve-Path $CaminhoArquivo).Path
    $NomeArquivo = [System.IO.Path]::GetFileName($ArquivoFull)
    $NomeBase = [System.IO.Path]::GetFileNameWithoutExtension($ArquivoFull)
    $Extensao = [System.IO.Path]::GetExtension($ArquivoFull)
    $PastaResultado = Join-Path $PastaSaida $NomeBase
    $ArquivoSaida = Join-Path $PastaResultado "$NomeBase-normalizado$Extensao"

    if (-not (Test-Path $PastaResultado)) {
        New-Item -ItemType Directory -Path $PastaResultado -Force | Out-Null
    }

    $pct = [int]((($Atual - 1) / $Total) * 100)
    Write-Progress -Activity "Normalizando Áudio (-14 LUFS) — LUIS MEDIA TOOLS" `
                   -Status "Processando [$Atual/$Total]: $NomeArquivo" `
                   -PercentComplete $pct

    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "[$Atual/$Total] Normalizando: $NomeArquivo" -ForegroundColor Cyan
    Write-Host "Alvo: -14 LUFS | True Peak: -1.5 dBFS" -ForegroundColor DarkGray
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan

    # Se for video, preserva a trilha visual intacta (-c:v copy) e normaliza apenas a trilha sonora
    if (@(".mp4", ".mkv", ".mov", ".webm") -contains $Extensao.ToLower()) {
        & ffmpeg -y -i "$ArquivoFull" -c:v copy -af "$FiltroLoudnorm" -c:a aac -b:a 192k "$ArquivoSaida" -loglevel error
    } else {
        # Se for audio puro (wav, mp3), processa como audio de alta qualidade
        & ffmpeg -y -i "$ArquivoFull" -af "$FiltroLoudnorm" "$ArquivoSaida" -loglevel error
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO ao processar: $NomeArquivo" -ForegroundColor Red
        return
    }

    Write-Host "[OK] Concluido: $ArquivoSaida" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  NORMALIZAÇÃO DE VOLUME BROADCAST (-14 LUFS)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($Arquivo)) {
    if (-not (Test-Path $Arquivo)) {
        Write-Host "ERRO: Arquivo nao encontrado: $Arquivo" -ForegroundColor Red
        exit 1
    }
    Normalizar-Arquivo -CaminhoArquivo $Arquivo -Atual 1 -Total 1
    Write-Progress -Activity "Normalizando Áudio" -Completed
} else {
    $exts = @(".mp4", ".mkv", ".mov", ".avi", ".webm", ".wav", ".mp3")
    $arquivos = Get-ChildItem -Path $PastaEntrada -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name

    if ($null -eq $arquivos -or $arquivos.Count -eq 0) {
        Write-Host "Nenhum arquivo encontrado em: $PastaEntrada" -ForegroundColor Yellow
        exit 0
    }

    $total = $arquivos.Count
    Write-Host "Encontrados $total arquivo(s) para normalizacao.`n" -ForegroundColor Green

    $i = 1
    foreach ($item in $arquivos) {
        Normalizar-Arquivo -CaminhoArquivo $item.FullName -Atual $i -Total $total
        $i++
    }

    Write-Progress -Activity "Normalizando Áudio" -Status "Concluído!" -PercentComplete 100 -Completed
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "    TODOS OS VOLUMES FORAM EQUALIZADOS!   " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
[System.Console]::Beep(1000, 200)