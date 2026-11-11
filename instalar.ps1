#Requires -Version 5.1
<#
.SYNOPSIS
    Instala o LUIS MEDIA TOOLS no Windows (uma vez so).

.DESCRIPTION
    1. Confere o Python 3.10+ (oferece instalar via winget se faltar)
    2. Cria o ambiente isolado .venv na pasta do programa
    3. Instala o motor luismedia com o Whisper (faster-whisper)
    4. Confere FFmpeg e Ollama (oferece instalar via winget) e baixa o modelo de IA
    5. Roda o diagnostico final (luismedia doctor)

    Pode ser rodado de novo a qualquer momento: so instala o que faltar.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\instalar.ps1
#>
param(
    [string]$ModeloIA = "llama3.2:3b",
    [switch]$SemIA
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raiz = $PSScriptRoot
Set-Location -LiteralPath $raiz

function Titulo([string]$t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }
function Ok([string]$t) { Write-Host "  [OK] $t" -ForegroundColor Green }
function Aviso([string]$t) { Write-Host "  [!]  $t" -ForegroundColor Yellow }
function Perguntar([string]$t) { return ((Read-Host "  $t [S/n]") -notmatch '^[nN]') }
function Tem([string]$cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Atualizar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Instalar-Winget([string]$id, [string]$nome) {
    if (-not (Tem "winget")) { Aviso "winget indisponivel. Instale $nome manualmente."; return $false }
    if (-not (Perguntar "Instalar $nome agora (winget)?")) { return $false }
    & winget install --id $id -e --accept-source-agreements --accept-package-agreements
    Atualizar-Path
    return ($LASTEXITCODE -eq 0)
}

Write-Host "LUIS MEDIA TOOLS - instalacao" -ForegroundColor Cyan
Write-Host "Pasta: $raiz"

# 1. Python ---------------------------------------------------------------
Titulo "Python"
function Python-Base {
    foreach ($c in @(@("py", "-3"), @("python"))) {
        if (Tem $c[0]) {
            $pre = @(); if ($c.Count -gt 1) { $pre = $c[1..($c.Count - 1)] }
            $v = & $c[0] @pre -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]"3.10") { return $c }
        }
    }
    return $null
}
$py = Python-Base
if (-not $py) {
    Aviso "Python 3.10 ou mais novo nao encontrado."
    if (Instalar-Winget "Python.Python.3.12" "Python 3.12") { $py = Python-Base }
    if (-not $py) { throw "Instale o Python 3.10+ (python.org) marcando 'Add to PATH' e rode este script de novo." }
}
Ok ("Python encontrado: " + ($py -join " "))

# 2. Ambiente virtual -----------------------------------------------------
Titulo "Ambiente isolado (.venv)"
$venvPy = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    $pre = @(); if ($py.Count -gt 1) { $pre = $py[1..($py.Count - 1)] }
    & $py[0] @pre -m venv (Join-Path $raiz ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar o ambiente virtual." }
}
Ok ".venv pronto"

# 3. Motor luismedia ------------------------------------------------------
Titulo "Motor LUIS MEDIA + Whisper"
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e "$raiz[whisper]" --quiet
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o motor. Veja a mensagem acima." }
Ok ("luismedia " + (& $venvPy -m luismedia --version))

# 4. FFmpeg ---------------------------------------------------------------
Titulo "FFmpeg"
if (Tem "ffmpeg") { Ok "FFmpeg no PATH" }
elseif (Instalar-Winget "Gyan.FFmpeg" "FFmpeg") { Ok "FFmpeg instalado (abra um novo terminal se o doctor nao achar)" }
else { Aviso "Sem FFmpeg o programa nao funciona. Baixe em https://www.gyan.dev/ffmpeg/builds/" }

# 5. Ollama (opcional) ----------------------------------------------------
if (-not $SemIA) {
    Titulo "IA local (Ollama, opcional)"
    if (-not (Tem "ollama")) {
        Aviso "Ollama nao encontrado. Sem ele: sem resumo, quiz e cortes; o resto funciona."
        [void](Instalar-Winget "Ollama.Ollama" "Ollama")
    }
    if (Tem "ollama") {
        Write-Host "  Baixando o modelo $ModeloIA (~2 GB na primeira vez)..."
        & ollama pull $ModeloIA
        if ($LASTEXITCODE -eq 0) { Ok "Modelo $ModeloIA pronto" } else { Aviso "Nao consegui baixar o modelo. Abra o Ollama e rode: ollama pull $ModeloIA" }
    }
}

# 6. Diagnostico ----------------------------------------------------------
Titulo "Diagnostico"
& $venvPy -m luismedia doctor
Write-Host "`nPronto. Abra o programa com: .\luis-media.ps1 (opcao A) ou .\pipeline-completo.ps1" -ForegroundColor Green
