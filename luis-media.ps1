# Roda sempre a partir da pasta do programa (os scripts sao chamados por caminho relativo)
Set-Location -LiteralPath $PSScriptRoot

function Mostrar-Menu {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "                      LUIS MEDIA TOOLS                      " -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  [S] CRIAR / COMPILAR SLIDES DA AULA (Markdown -> HTML)" -ForegroundColor Yellow
    Write-Host "  [A] ABRIR O APP (processar aulas, slides, diagnostico)" -ForegroundColor Green
    Write-Host "  [D] DIAGNOSTICO (FFmpeg, GPU, Whisper, Ollama)" -ForegroundColor Green
    Write-Host "  [I] INSTALAR / ATUALIZAR DEPENDENCIAS" -ForegroundColor Green
    Write-Host "------------------------------------------------------------" -ForegroundColor DarkGray
    Write-Host "  MODULOS INDIVIDUAIS (POS-PRODUCAO):" -ForegroundColor DarkGray
    Write-Host "   1. Processar Aulas em Lote (Transcricao + Legendas)" -ForegroundColor White
    Write-Host "   2. Regenerar Legendas a partir de JSON" -ForegroundColor White
    Write-Host "   3. Transcrever Arquivo Unico" -ForegroundColor White
    Write-Host "   4. Cortar Silencios de Audios/Aulas (Remover Pausas)" -ForegroundColor White
    Write-Host "   5. Unificar Todos os Audios da Aula em Um So" -ForegroundColor White
    Write-Host "   6. Normalizar Volume para YouTube/Cursos (-14 LUFS)" -ForegroundColor White
    Write-Host "   7. Organizar Saida em Subpastas Categorizadas" -ForegroundColor White
    Write-Host "   8. Gerar Entregaveis Finais (Relatorio, ASS, Apostila, ZIP)" -ForegroundColor White
    Write-Host "   9. Queimar Legenda no Video MP4 (Hardsub)" -ForegroundColor White
    Write-Host "  10. Ajuda: O que cada opcao faz?" -ForegroundColor Cyan
    Write-Host "   0. Sair" -ForegroundColor DarkGray
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Mostrar-Ajuda {
    Clear-Host
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "             GUIA DE FERRAMENTAS - LUIS MEDIA TOOLS         " -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "[S] Slides: Converte roteiro markdown em apresentacao HTML interativa." -ForegroundColor Yellow
    Write-Host "[A] Piloto Automatico: Roda da transcricao ao ZIP final automaticamente." -ForegroundColor Green
    Write-Host "[D] Diagnostico: Confere se FFmpeg, GPU, Whisper e Ollama estao prontos." -ForegroundColor Green
    Write-Host "[I] Instalar: Prepara Python, motor, FFmpeg e modelo de IA (rode uma vez)." -ForegroundColor Green
    Write-Host "[1] Processar Aulas: Transcreve e legenda arquivos da pasta entrada." -ForegroundColor Yellow
    Write-Host "[2] Regenerar Legendas: Recalcula quebras de texto pelo .json." -ForegroundColor Yellow
    Write-Host "[3] Transcrever Unico: Transcreve apenas 1 arquivo pontual." -ForegroundColor Yellow
    Write-Host "[4] Cortar Silencios: Enxuga trechos mudos com FFmpeg (-40dB)." -ForegroundColor Yellow
    Write-Host "[5] Unificar Audios: Une todos os audios em uma faixa mestre continua." -ForegroundColor Yellow
    Write-Host "[6] Normalizar Volume: Calibra o ganho em -14 LUFS (EBU R128)." -ForegroundColor Yellow
    Write-Host "[7] Organizar Saida: Separa em 1_Legendas, 2_Audio_Bruto, etc." -ForegroundColor Yellow
    Write-Host "[8] Gerar Entregaveis: Cria .ASS estilizado, capitulos, apostila e ZIP." -ForegroundColor Yellow
    Write-Host "[9] Queimar Legenda: Exporta o MP4 finalizado com a legenda embutida." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Pressione qualquer tecla para voltar ao menu..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

do {
    Mostrar-Menu
    $opcao = Read-Host "Escolha uma opcao [S, A, D, I, 0-10]"

    switch -Regex ($opcao) {
        "^[sS]$" { .\gerar-slides.ps1; Pause }
        "^[aA]$" {
            $pythonw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
            if (Test-Path -LiteralPath $pythonw) { Start-Process -FilePath $pythonw -ArgumentList "-m", "luismedia.gui" -WorkingDirectory $PSScriptRoot }
            else { .\pipeline-completo.ps1; Pause }
        }
        "^[dD]$" {
            $venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
            if (Test-Path -LiteralPath $venvPy) { & $venvPy -m luismedia doctor } else { Write-Host "Rode a opcao [I] primeiro." -ForegroundColor Yellow }
            Pause
        }
        "^[iI]$" { .\instalar.ps1; Pause }
        "^1$"    { .\processar-aula.ps1; Pause }
        "^2$"    {
            $json = Read-Host "Digite o caminho do arquivo .json"
            if (Test-Path $json) { .\gerar-legendas.ps1 -Json $json } else { Write-Host "Nao encontrado!" -ForegroundColor Red }
            Pause
        }
        "^3$"    {
            $arq = Read-Host "Digite o caminho do arquivo"
            if (Test-Path $arq) { .\transcrever.ps1 -Arquivo $arq } else { Write-Host "Nao encontrado!" -ForegroundColor Red }
            Pause
        }
        "^4$"    { .\remover-silencio.ps1; Pause }
        "^5$"    { .\juntar-audios.ps1; Pause }
        "^6$"    { .\normalizar-audio.ps1; Pause }
        "^7$"    { .\organizar-saida.ps1; Pause }
        "^8$"    { .\gerar-entregaveis.ps1; Pause }
        "^9$"    { .\queimar-legenda.ps1; Pause }
        "^10$"   { Mostrar-Ajuda }
        "^0$"    { Write-Host "Saindo..." -ForegroundColor DarkGray; break }
        Default  { Write-Host "Opcao invalida!" -ForegroundColor Red; Start-Sleep -Seconds 1 }
    }
} while ($opcao -ne "0")