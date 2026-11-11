param(
    [Parameter(Mandatory=$false)]
    [string]$Arquivo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

# Parametros calibrados para aulas faladas:
# -40dB de corte para ruidos de fundo
# Silencios acima de 0.6s sao removidos
# Deixa 0.15s (150ms) de margem para manter a respiracao natural
$FiltroSilencio = "silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-40dB:leave_silence=0.15"

function Remover-SilencioArquivo {
    param(
        [string]$CaminhoArquivo,
        [int]$Atual = 1,
        [int]$Total = 1
    )

    $ArquivoFull = (Resolve-Path $CaminhoArquivo).Path
    $NomeArquivo = [System.IO.Path]::GetFileName($ArquivoFull)
    $NomeBase = [System.IO.Path]::GetFileNameWithoutExtension($ArquivoFull)
    $PastaResultado = Join-Path $PastaSaida $NomeBase
    $ArquivoSaida = Join-Path $PastaResultado "$NomeBase-sem-silencio.mp3"

    if (-not (Test-Path $PastaResultado)) {
        New-Item -ItemType Directory -Path $PastaResultado -Force | Out-Null
    }

    $pct = [int]((($Atual - 1) / $Total) * 100)
    Write-Progress -Activity "Removendo Silêncios — LUIS MEDIA TOOLS" `
                   -Status "Processando [$Atual/$Total]: $NomeArquivo" `
                   -PercentComplete $pct

    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "[$Atual/$Total] Cortando silêncios de: $NomeArquivo" -ForegroundColor Cyan
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan

    # Executa FFmpeg aplicando o filtro de remocao de pausas
    & ffmpeg -y -i "$ArquivoFull" -af "$FiltroSilencio" -vn -c:a libmp3lame -q:a 2 "$ArquivoSaida" -loglevel error

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO ao processar: $NomeArquivo" -ForegroundColor Red
        return
    }

    Write-Host "[OK] Gerado: $ArquivoSaida" -ForegroundColor Green
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "     REMOVEDOR DE SILÊNCIO (AUDIOAULA)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($Arquivo)) {
    if (-not (Test-Path $Arquivo)) {
        Write-Host "ERRO: Arquivo nao encontrado: $Arquivo" -ForegroundColor Red
        exit 1
    }
    Remover-SilencioArquivo -CaminhoArquivo $Arquivo -Atual 1 -Total 1
    Write-Progress -Activity "Removendo Silêncios" -Completed
} else {
    $exts = @(".mp4", ".mkv", ".mov", ".avi", ".webm", ".wav", ".mp3")
    $arquivos = Get-ChildItem -Path $PastaEntrada -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name

    if ($null -eq $arquivos -or $arquivos.Count -eq 0) {
        Write-Host "Nenhum arquivo encontrado em: $PastaEntrada" -ForegroundColor Yellow
        exit 0
    }

    $total = $arquivos.Count
    Write-Host "Encontrados $total arquivo(s) para tratamento.`n" -ForegroundColor Green

    $i = 1
    foreach ($item in $arquivos) {
        Remover-SilencioArquivo -CaminhoArquivo $item.FullName -Atual $i -Total $total
        $i++
    }

    Write-Progress -Activity "Removendo Silêncios" -Status "Concluído!" -PercentComplete 100 -Completed
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "       TODOS OS SILÊNCIOS CORTADOS!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
[System.Console]::Beep(1000, 200)