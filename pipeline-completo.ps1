$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "      PILOTO AUTOMÁTICO — PIPELINE COMPLETO (1 CLIQUE)   " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Este modo vai executar sequencialmente:" -ForegroundColor White
Write-Host "  1. Transcrição Whisper + Legendas balanceadas" -ForegroundColor DarkGray
Write-Host "  2. Unificação de todos os áudios da aula (Master)" -ForegroundColor DarkGray
Write-Host "  3. Normalização de volume broadcast (-14 LUFS)" -ForegroundColor DarkGray
Write-Host "  4. Organização das pastas categorizadas" -ForegroundColor DarkGray
Write-Host "  5. Geração de relatórios, capítulos, apostila e ZIP" -ForegroundColor DarkGray
Write-Host ""

$confirma = Read-Host "Deseja iniciar o Pipeline Completo agora? (S/N)"
if ($confirma -notmatch '^[sSyY]$') {
    Write-Host "Operação cancelada." -ForegroundColor DarkGray
    exit 0
}

$tempoInicio = Get-Date

# ETAPA 1: Processar Lote (Transcrição e Legendas)
Write-Host "`n>>> [ETAPA 1/5] Processando transcrição e legendas... <<<" -ForegroundColor Yellow
& "$PastaScript\processar-aula.ps1"

# ETAPA 2: Unificar Áudios
Write-Host "`n>>> [ETAPA 2/5] Unificando áudios da aula... <<<" -ForegroundColor Yellow
& "$PastaScript\juntar-audios.ps1"

# ETAPA 3: Normalizar Volume
Write-Host "`n>>> [ETAPA 3/5] Aplicando normalização broadcast (-14 LUFS)... <<<" -ForegroundColor Yellow
& "$PastaScript\normalizar-audio.ps1"

# ETAPA 4: Organizar Pastas
Write-Host "`n>>> [ETAPA 4/5] Organizando estrutura de pastas de saída... <<<" -ForegroundColor Yellow
& "$PastaScript\organizar-saida.ps1"

# ETAPA 5: Gerar Entregáveis e ZIP
Write-Host "`n>>> [ETAPA 5/5] Gerando relatórios, capítulos, apostila e ZIP... <<<" -ForegroundColor Yellow
& "$PastaScript\gerar-entregaveis.ps1"

$tempoFim = Get-Date
$duracao = $tempoFim - $tempoInicio
$tempoFormatado = "{0:D2}h {1:D2}m {2:D2}s" -f $duracao.Hours, $duracao.Minutes, $duracao.Seconds

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "       PIPELINE COMPLETO CONCLUÍDO COM SUCESSO!          " -ForegroundColor Green
Write-Host "       Tempo total de execução: $tempoFormatado          " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green

[System.Console]::Beep(800, 200)
[System.Console]::Beep(1000, 200)
[System.Console]::Beep(1300, 400)