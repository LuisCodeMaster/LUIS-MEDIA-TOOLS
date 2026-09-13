Clear-Host
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "               LUIS MEDIA TOOLS                " -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "  1. Processar Aulas em Lote (Transcricao + Legendas)" -ForegroundColor White
Write-Host "  2. Gerar/Regenerar Legendas a partir de JSON" -ForegroundColor White
Write-Host "  3. Transcrever Arquivo Unico" -ForegroundColor White
Write-Host "  4. Cortar Silencios de Audios/Aulas (Remover Pausas)" -ForegroundColor White
Write-Host "  5. Unificar Todos os Audios da Aula em Um So" -ForegroundColor Yellow
Write-Host "  6. Sair" -ForegroundColor DarkGray
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

$opcao = Read-Host "Escolha uma opcao [1-6]"

switch ($opcao) {
    "1" {
        .\processar-aula.ps1
    }
    "2" {
        $json = Read-Host "Digite o caminho completo ou relativo do arquivo .json"
        if (Test-Path $json) {
            .\gerar-legendas.ps1 -Json $json
        } else {
            Write-Host "Arquivo nao encontrado!" -ForegroundColor Red
        }
    }
    "3" {
        $arq = Read-Host "Digite o caminho do arquivo de video/audio"
        if (Test-Path $arq) {
            .\transcrever.ps1 -Arquivo $arq
        } else {
            Write-Host "Arquivo nao encontrado!" -ForegroundColor Red
        }
    }
    "4" {
        .\remover-silencio.ps1
    }
    "5" {
        .\juntar-audios.ps1
    }
    "6" {
        Write-Host "Saindo..." -ForegroundColor DarkGray
        exit 0
    }
    Default {
        Write-Host "Opcao invalida!" -ForegroundColor Red
    }
}