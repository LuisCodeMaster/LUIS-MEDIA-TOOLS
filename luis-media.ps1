# ==========================================
# LUIS MEDIA TOOLS
# MENU PRINCIPAL
# ==========================================

$ErrorActionPreference = "Stop"

function Mostrar-Menu {

    Clear-Host

    Write-Host "================================" -ForegroundColor Cyan
    Write-Host "       LUIS MEDIA TOOLS" -ForegroundColor Cyan
    Write-Host "================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[1] Processar aula"
    Write-Host "[2] Processar Short"
    Write-Host "[3] Transcrever"
    Write-Host "[4] Tratar audio"
    Write-Host "[5] Cortar video"
    Write-Host "[6] Gerar material"
    Write-Host "[7] Criar thumbnail"
    Write-Host "[0] Sair"
    Write-Host ""
}

function Pausar {
    Write-Host ""
    Read-Host "Pressione ENTER para continuar"
}

do {

    Mostrar-Menu

    $opcao = Read-Host "Escolha uma opcao"

    switch ($opcao) {

        "1" {
            Clear-Host
            Write-Host "=== PROCESSAR AULA ===" -ForegroundColor Cyan
            Write-Host ""

            $arquivo = Read-Host "Digite o caminho do video"

            if (Test-Path $arquivo) {
                & "$PSScriptRoot\processar-aula.ps1" $arquivo
            }
            else {
                Write-Host "Arquivo nao encontrado." -ForegroundColor Red
            }

            Pausar
        }

        "2" {
            Clear-Host
            Write-Host "=== PROCESSAR SHORT ===" -ForegroundColor Cyan
            Write-Host ""

            if (Test-Path "$PSScriptRoot\processar-short.ps1") {
                $arquivo = Read-Host "Digite o caminho do Short"
                & "$PSScriptRoot\processar-short.ps1" $arquivo
            }
            else {
                Write-Host "O modulo processar-short.ps1 ainda nao foi criado." -ForegroundColor Yellow
            }

            Pausar
        }

        "3" {
            Clear-Host
            Write-Host "=== TRANSCRIBER ===" -ForegroundColor Cyan
            Write-Host ""

            $arquivo = Read-Host "Digite o caminho do audio/video"

            if (Test-Path $arquivo) {
                & "$PSScriptRoot\transcrever.ps1" $arquivo
            }
            else {
                Write-Host "Arquivo nao encontrado." -ForegroundColor Red
            }

            Pausar
        }

        "4" {
            Clear-Host
            Write-Host "=== TRATAR AUDIO ===" -ForegroundColor Cyan
            Write-Host ""

            if (Test-Path "$PSScriptRoot\tratar-audio.ps1") {
                $arquivo = Read-Host "Digite o caminho do audio/video"
                & "$PSScriptRoot\tratar-audio.ps1" $arquivo
            }
            else {
                Write-Host "O modulo tratar-audio.ps1 ainda nao foi criado." -ForegroundColor Yellow
            }

            Pausar
        }

        "5" {
            Clear-Host
            Write-Host "=== CORTAR VIDEO ===" -ForegroundColor Cyan
            Write-Host ""

            if (Test-Path "$PSScriptRoot\cortar-video.ps1") {
                $arquivo = Read-Host "Digite o caminho do video"
                & "$PSScriptRoot\cortar-video.ps1" $arquivo
            }
            else {
                Write-Host "O modulo cortar-video.ps1 ainda nao foi criado." -ForegroundColor Yellow
            }

            Pausar
        }

        "6" {
            Clear-Host
            Write-Host "=== GERAR MATERIAL ===" -ForegroundColor Cyan
            Write-Host ""

            if (Test-Path "$PSScriptRoot\gerar-material.ps1") {
                $arquivo = Read-Host "Digite o caminho da transcricao"
                & "$PSScriptRoot\gerar-material.ps1" $arquivo
            }
            else {
                Write-Host "O modulo gerar-material.ps1 ainda nao foi criado." -ForegroundColor Yellow
            }

            Pausar
        }

        "7" {
            Clear-Host
            Write-Host "=== CRIAR THUMBNAIL ===" -ForegroundColor Cyan
            Write-Host ""

            if (Test-Path "$PSScriptRoot\criar-thumbnail.ps1") {
                $arquivo = Read-Host "Digite o caminho do video/imagem"
                & "$PSScriptRoot\criar-thumbnail.ps1" $arquivo
            }
            else {
                Write-Host "O modulo criar-thumbnail.ps1 ainda nao foi criado." -ForegroundColor Yellow
            }

            Pausar
        }

        "0" {
            Clear-Host
            Write-Host "Saindo do LUIS MEDIA TOOLS..." -ForegroundColor Cyan
            Write-Host ""
        }

        default {
            Write-Host ""
            Write-Host "Opcao invalida." -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }

} while ($opcao -ne "0")