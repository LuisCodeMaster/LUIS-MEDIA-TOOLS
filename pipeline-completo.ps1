$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "      PILOTO AUTOMATICO - PIPELINE COMPLETO (1 CLIQUE)   " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Este modo vai executar sequencialmente:" -ForegroundColor White
Write-Host "  1. Transcricao Whisper + Legendas balanceadas" -ForegroundColor DarkGray
Write-Host "  2. Unificacao de todos os audios da aula (Master)" -ForegroundColor DarkGray
Write-Host "  3. Normalizacao de volume broadcast (-14 LUFS)" -ForegroundColor DarkGray
Write-Host "  4. Organizacao das pastas categorizadas" -ForegroundColor DarkGray
Write-Host "  5. Geracao de relatorios, capitulos, apostila e ZIP" -ForegroundColor DarkGray
Write-Host ""

$confirma = Read-Host "Deseja iniciar o Pipeline Completo agora? (S/N)"
if ($confirma -notmatch '^[sSyY]$') {
    Write-Host "Operacao cancelada." -ForegroundColor DarkGray
    exit 0
}

$tempoInicio = Get-Date

# ETAPA 1: Processar Lote (Transcricao e Legendas)
Write-Host ""
Write-Host "=== [ETAPA 1/5] Processando transcricao e legendas... ===" -ForegroundColor Yellow
& "$PastaScript\processar-aula.ps1"

# ETAPA 2: Unificar Audios
Write-Host ""
Write-Host "=== [ETAPA 2/5] Unificando audios da aula... ===" -ForegroundColor Yellow
& "$PastaScript\juntar-audios.ps1"

# ETAPA 3: Normalizar Volume
Write-Host ""
Write-Host "=== [ETAPA 3/5] Aplicando normalizacao broadcast (-14 LUFS)... ===" -ForegroundColor Yellow
& "$PastaScript\normalizar-audio.ps1"

# ETAPA 4: Organizar Pastas
Write-Host ""
Write-Host "=== [ETAPA 4/5] Organizando estrutura de pastas de saida... ===" -ForegroundColor Yellow
& "$PastaScript\organizar-saida.ps1"

# ETAPA 5: Gerar Entregaveis e ZIP
Write-Host ""
Write-Host "=== [ETAPA 5/5] Gerando relatorios, capitulos, apostila e ZIP... ===" -ForegroundColor Yellow
& "$PastaScript\gerar-entregaveis.ps1"

$tempoFim = Get-Date
$duracao = $tempoFim - $tempoInicio
$tempoFormatado = "{0:D2}h {1:D2}m {2:D2}s" -f $duracao.Hours, $duracao.Minutes, $duracao.Seconds

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "       PIPELINE COMPLETO CONCLUIDO COM SUCESSO!          " -ForegroundColor Green
Write-Host "       Tempo total de execucao: $tempoFormatado          " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green

[System.Console]::Beep(800, 200)
[System.Console]::Beep(1000, 200)
[System.Console]::Beep(1300, 400)