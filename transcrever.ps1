param(
    [Parameter(Mandatory=$true)]
    [string]$Arquivo,

    [string]$Model = "small",

    [string]$Language = "Portuguese"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       LUIS MEDIA TOOLS - WHISPER" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ========================================
# VERIFICAR ARQUIVO
# ========================================

if (-not (Test-Path $Arquivo)) {
    Write-Host "ERRO: Arquivo nao encontrado:" -ForegroundColor Red
    Write-Host $Arquivo
    exit 1
}

$ArquivoFull = (Resolve-Path $Arquivo).Path
$Nome = [System.IO.Path]::GetFileNameWithoutExtension($ArquivoFull)

Write-Host "Arquivo:" -ForegroundColor Yellow
Write-Host $ArquivoFull
Write-Host ""

# ========================================
# VERIFICAR FFMPEG
# ========================================

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: FFmpeg nao encontrado." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] FFmpeg encontrado" -ForegroundColor Green

# ========================================
# VERIFICAR WHISPER
# ========================================

if (-not (Get-Command whisper -ErrorAction SilentlyContinue)) {
    Write-Host "ERRO: Whisper nao encontrado." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Whisper encontrado" -ForegroundColor Green
Write-Host ""

# ========================================
# CRIAR PASTA DE SAIDA
# ========================================

$PastaSaida = Join-Path $PSScriptRoot "saida"
$PastaResultado = Join-Path $PastaSaida $Nome

if (-not (Test-Path $PastaSaida)) {
    New-Item -ItemType Directory -Path $PastaSaida | Out-Null
}

if (-not (Test-Path $PastaResultado)) {
    New-Item -ItemType Directory -Path $PastaResultado | Out-Null
}

Write-Host "Pasta de saida:" -ForegroundColor Yellow
Write-Host $PastaResultado
Write-Host ""

# ========================================
# EXTRAIR AUDIO
# ========================================

$Audio = Join-Path $PastaResultado "$Nome.wav"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " EXTRAINDO AUDIO" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

ffmpeg `
    -y `
    -i "$ArquivoFull" `
    -vn `
    -ac 1 `
    -ar 16000 `
    -c:a pcm_s16le `
    "$Audio"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO ao extrair audio." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] Audio extraido" -ForegroundColor Green
Write-Host ""

# ========================================
# TRANSCRICAO
# ========================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " TRANSCRIBINDO COM WHISPER" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Modelo: $Model" -ForegroundColor Yellow
Write-Host "Idioma: $Language" -ForegroundColor Yellow
Write-Host "Word timestamps: ATIVADO" -ForegroundColor Yellow
Write-Host ""

whisper "$Audio" `
    --model $Model `
    --language $Language `
    --word_timestamps True `
    --output_format all `
    --output_dir "$PastaResultado"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO durante a transcricao." -ForegroundColor Red
    exit 1
}

# ========================================
# VERIFICAR RESULTADOS
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " TRANSCRICAO CONCLUIDA" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$Arquivos = @(
    "$Nome.txt",
    "$Nome.srt",
    "$Nome.vtt",
    "$Nome.tsv",
    "$Nome.json"
)

foreach ($ArquivoResultado in $Arquivos) {

    $Caminho = Join-Path $PastaResultado $ArquivoResultado

    if (Test-Path $Caminho) {
        Write-Host "[OK] $ArquivoResultado" -ForegroundColor Green
    }
    else {
        Write-Host "[--] $ArquivoResultado nao encontrado" -ForegroundColor DarkYellow
    }
}

# ========================================
# GERAR LEGENDAS OTIMIZADAS
# ========================================

$GerarLegendas = Join-Path $PSScriptRoot "gerar-legendas.ps1"

if (Test-Path $GerarLegendas) {

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host " GERANDO LEGENDAS OTIMIZADAS" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    & $GerarLegendas "$PastaResultado\$Nome.json"

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[OK] Legendas otimizadas geradas." -ForegroundColor Green
    }
    else {
        Write-Host ""
        Write-Host "[AVISO] Nao foi possivel gerar as legendas otimizadas." -ForegroundColor Yellow
    }
}

# ========================================
# FINAL
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "        PROCESSO CONCLUIDO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Arquivos em:" -ForegroundColor Yellow
Write-Host $PastaResultado
Write-Host ""

Write-Host "Proximo passo:" -ForegroundColor Cyan
Write-Host "O gerar-legendas.ps1 usa o JSON para criar legendas"
Write-Host "com timestamps por palavra."
Write-Host ""