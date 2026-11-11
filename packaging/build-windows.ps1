#Requires -Version 5.1
<#
.SYNOPSIS
    Gera a versao portatil para Windows: pasta dist\LUIS-MEDIA-TOOLS com o motor
    empacotado (motor\luismedia.exe), FFmpeg embutido e a interface.

.DESCRIPTION
    O cliente final nao precisa instalar Python. Precisa apenas, se quiser IA, do Ollama.

    FFmpeg: informe a pasta com ffmpeg.exe e ffprobe.exe em -FFmpegDir. Atencao a licenca:
    builds com libx264 sao GPL. Para distribuir junto de um produto fechado, use um build
    LGPL (encoders de GPU continuam funcionando) ou cumpra os termos da GPL.

.EXAMPLE
    .\packaging\build-windows.ps1 -FFmpegDir C:\ffmpeg\bin
#>
param(
    [Parameter(Mandatory = $true)][string]$FFmpegDir,
    [string]$Saida = (Join-Path $PSScriptRoot "..\dist\LUIS-MEDIA-TOOLS")
)
$ErrorActionPreference = "Stop"
$raiz = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $raiz

foreach ($b in "ffmpeg.exe", "ffprobe.exe") {
    if (-not (Test-Path -LiteralPath (Join-Path $FFmpegDir $b))) { throw "$b nao encontrado em $FFmpegDir" }
}

python -m pip install --upgrade pyinstaller -e ".[whisper]"
if ($LASTEXITCODE -ne 0) { throw "falha ao instalar dependencias de build" }

python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot "luismedia.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

if (Test-Path -LiteralPath $Saida) { Remove-Item -LiteralPath $Saida -Recurse -Force }
New-Item -ItemType Directory -Path $Saida | Out-Null
Copy-Item -Recurse (Join-Path $raiz "dist\luismedia") (Join-Path $Saida "motor")
New-Item -ItemType Directory -Path (Join-Path $Saida "motor\bin") -Force | Out-Null
Copy-Item (Join-Path $FFmpegDir "ffmpeg.exe"), (Join-Path $FFmpegDir "ffprobe.exe") (Join-Path $Saida "motor\bin")
Copy-Item (Join-Path $raiz "*.ps1"), (Join-Path $raiz "README.md"), (Join-Path $raiz "LICENSE") $Saida
Copy-Item -Recurse (Join-Path $raiz "profiles") $Saida

& (Join-Path $Saida "motor\luismedia.exe") doctor
Write-Host "`nPronto: $Saida" -ForegroundColor Green
