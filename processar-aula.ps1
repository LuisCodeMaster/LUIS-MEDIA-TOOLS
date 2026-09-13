param(
    [Parameter(Mandatory=$true)]
    [string]$Arquivo
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "        LUIS MEDIA TOOLS" -ForegroundColor Cyan
Write-Host "          PROCESSAR AULA" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $Arquivo)) {
    Write-Host "ERRO: Arquivo nao encontrado." -ForegroundColor Red
    exit 1
}

$ArquivoFull = (Resolve-Path $Arquivo).Path
$Nome = [System.IO.Path]::GetFileNameWithoutExtension($Arquivo)
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSaida = Join-Path $PastaScript "saida"
$PastaResultado = Join-Path $PastaSaida $Nome

if (-not (Test-Path $PastaResultado)) {
    New-Item -ItemType Directory -Path $PastaResultado | Out-Null
}

Write-Host "[1/2] Processando transcricao..." -ForegroundColor Cyan

& "$PastaScript\transcrever.ps1" "$ArquivoFull"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERRO na transcricao." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/2] Organizando arquivos..." -ForegroundColor Cyan

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "           AULA PROCESSADA!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Resultado salvo em:"
Write-Host $PastaResultado -ForegroundColor Yellow
Write-Host ""