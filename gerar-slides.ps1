param(
    [Parameter(Mandatory=$false)]
    [string]$ArquivoRoteiro
)

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "     ESTUDIO EDITORIAL DE SLIDES - LUIS MEDIA TOOLS      " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Criar novo roteiro com Llama Local (Ollama)"
Write-Host "2. Compilar roteiro existente (slides/roteiro-aula.md)"
Write-Host ""
$opcao = Read-Host "Escolha uma opcao (1 ou 2)"

$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSlides = Join-Path $PastaScript "slides"

if (-not (Test-Path $PastaSlides)) {
    New-Item -ItemType Directory -Path $PastaSlides -Force | Out-Null
}

$caminhoMd = Join-Path $PastaSlides "roteiro-aula.md"

if ($opcao -eq "1") {
    $tema = Read-Host "Digite o tema ou resumo da aula"
    python (Join-Path $PastaScript "gerar_roteiro_ia.py") "$tema"
}

python (Join-Path $PastaScript "slides_engine.py") "$caminhoMd"

$ArquivoHtml = [System.IO.Path]::ChangeExtension($caminhoMd, ".html")

Write-Host ""
$abrir = Read-Host "Deseja abrir os slides no navegador agora? (S/N)"
if ($abrir -match '^[sSyY]$') {
    Start-Process $ArquivoHtml
}