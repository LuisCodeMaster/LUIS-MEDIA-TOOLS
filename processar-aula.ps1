param(
    [Parameter(Mandatory=$false)]
    [string]$CaminhoAlvo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"
$exts = @(".mp4", ".mkv", ".mov", ".avi", ".webm")

function Processar-Video {
    param(
        [string]$CaminhoArquivo,
        [string]$NomePastaAula,
        [int]$Atual,
        [int]$Total
    )

    $ArquivoFull = (Resolve-Path $CaminhoArquivo).Path
    $NomeArquivo = [System.IO.Path]::GetFileName($ArquivoFull)
    $NomeBase = [System.IO.Path]::GetFileNameWithoutExtension($ArquivoFull)
    
    $pct = [int]((($Atual - 1) / $Total) * 100)
    $restantes = $Total - $Atual

    $tituloTag = if (-not [string]::IsNullOrWhiteSpace($NomePastaAula)) { "$NomePastaAula -> " } else { "" }
    $host.UI.RawUI.WindowTitle = "[$Atual/$Total] $tituloTag$NomeArquivo"
    Write-Progress -Activity "LUIS MEDIA TOOLS" `
                   -Status "Video $Atual de ${Total}: $NomeArquivo ($restantes restantes)" `
                   -PercentComplete $pct

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host " [$Atual/$Total] $NomeArquivo" -ForegroundColor Cyan
    if (-not [string]::IsNullOrWhiteSpace($NomePastaAula)) {
        Write-Host " Pasta da Aula: $NomePastaAula" -ForegroundColor Yellow
        Write-Host " Destino: saida\$NomePastaAula\$NomeBase" -ForegroundColor DarkGray
    } else {
        Write-Host " Destino: saida\$NomeBase" -ForegroundColor DarkGray
    }
    Write-Host "==========================================" -ForegroundColor Cyan

    # Chama o transcrever.ps1 padrao apenas com -Arquivo
    & "$PastaScript\transcrever.ps1" -Arquivo "$ArquivoFull"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO ao processar: $NomeArquivo" -ForegroundColor Red
        return
    }

    # Se estiver dentro de uma subpasta de aula (ex: Aula 1), move da saida padrao para a pasta da aula
    if (-not [string]::IsNullOrWhiteSpace($NomePastaAula)) {
        $origemPadrao = Join-Path $PastaSaida $NomeBase
        $destinoFinalPasta = Join-Path $PastaSaida $NomePastaAula
        $destinoFinal = Join-Path $destinoFinalPasta $NomeBase

        if (-not (Test-Path $destinoFinalPasta)) {
            New-Item -ItemType Directory -Path $destinoFinalPasta -Force | Out-Null
        }

        if (Test-Path $origemPadrao) {
            if (Test-Path $destinoFinal) { Remove-Item -Path $destinoFinal -Recurse -Force }
            Move-Item -Path $origemPadrao -Destination $destinoFinal -Force
        }
    }

    Write-Host "[OK] Concluido: $NomeBase" -ForegroundColor Green
}

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "          LUIS MEDIA TOOLS - SELEÇÃO DE AULAS            " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

$subpastas = Get-ChildItem -Path $PastaEntrada -Directory | Sort-Object Name
$arquivosRaiz = Get-ChildItem -Path $PastaEntrada -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name

$listaAulas = @()
$indice = 1

foreach ($p in $subpastas) {
    $vids = Get-ChildItem -Path $p.FullName -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name
    $qtd = $vids.Count
    $textoQtd = if ($qtd -eq 1) { "1 video" } else { "$qtd videos" }

    $listaAulas += [PSCustomObject]@{
        Numero      = $indice
        NomeExibido = $p.Name
        NomePasta   = $p.Name
        Videos      = $vids
        Qtd         = $qtd
    }
    $indice++
}

if ($arquivosRaiz.Count -gt 0) {
    $qtd = $arquivosRaiz.Count
    $textoQtd = if ($qtd -eq 1) { "1 video" } else { "$qtd videos" }
    
    $listaAulas += [PSCustomObject]@{
        Numero      = $indice
        NomeExibido = "Arquivos soltos em entrada/ (Raiz)"
        NomePasta   = ""
        Videos      = $arquivosRaiz
        Qtd         = $qtd
    }
    $indice++
}

if ($listaAulas.Count -eq 0) {
    Write-Host "Nenhum video encontrado na pasta entrada/ nem em subpastas." -ForegroundColor Yellow
    Write-Host "Coloque seus arquivos (.mp4, .mkv) dentro de: $PastaEntrada" -ForegroundColor DarkGray
    exit 0
}

Write-Host "Pastas e conteudos detectados:" -ForegroundColor White
Write-Host ""

foreach ($item in $listaAulas) {
    $tagQtd = if ($item.Qtd -eq 1) { "1 video" } else { "$($item.Qtd) videos" }
    Write-Host "  [$($item.Numero)] " -NoNewline -ForegroundColor Yellow
    Write-Host "$($item.NomeExibido) " -NoNewline -ForegroundColor White
    Write-Host "($tagQtd)" -ForegroundColor DarkGray
}

if ($listaAulas.Count -gt 1) {
    Write-Host "  [T] " -NoNewline -ForegroundColor Green
    Write-Host "Processar TODAS em sequencia" -ForegroundColor Green
}
Write-Host "  [0] " -NoNewline -ForegroundColor Red
Write-Host "Cancelar e voltar" -ForegroundColor Red
Write-Host ""

$escolha = Read-Host "Qual opcao voce deseja processar? [1-$($listaAulas.Count), T ou 0]"

if ($escolha -eq "0") {
    Write-Host "Operacao cancelada." -ForegroundColor DarkGray
    exit 0
}

$selecionadas = @()

if ($escolha -match '^[tT]$' -and $listaAulas.Count -gt 1) {
    $selecionadas = $listaAulas
} else {
    $num = 0
    if ([int]::TryParse($escolha, [ref]$num) -and $num -ge 1 -and $num -le $listaAulas.Count) {
        $selecionadas = @($listaAulas[$num - 1])
    } else {
        Write-Host "Opcao invalida!" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "---------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Voce selecionou para processamento:" -ForegroundColor White
foreach ($item in $selecionadas) {
    Write-Host " -> $($item.NomeExibido) ($($item.Qtd) videos)" -ForegroundColor Yellow
}
Write-Host "---------------------------------------------------------" -ForegroundColor Cyan
$confirma = Read-Host "Deseja iniciar o processamento agora? (S/N)"

if ($confirma -notmatch '^[sSyY]$') {
    Write-Host "Processamento cancelado pelo usuario." -ForegroundColor DarkGray
    exit 0
}

foreach ($aula in $selecionadas) {
    if ($aula.Qtd -eq 0) {
        Write-Host "Sem videos para processar em '$($aula.NomeExibido)'. Pulando..." -ForegroundColor DarkGray
        continue
    }

    Write-Host ""
    Write-Host ">>> Processando: $($aula.NomeExibido) ($($aula.Qtd) videos) <<<" -ForegroundColor Green

    $i = 1
    foreach ($vid in $aula.Videos) {
        Processar-Video -CaminhoArquivo $vid.FullName -NomePastaAula $aula.NomePasta -Atual $i -Total $aula.Qtd
        $i++
    }
}

Write-Progress -Activity "LUIS MEDIA TOOLS" -Completed
$host.UI.RawUI.WindowTitle = "LUIS MEDIA TOOLS - Finalizado!"

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "       TODOS OS PROCESSOS FORAM CONCLUIDOS!              " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
[System.Console]::Beep(800, 200)
[System.Console]::Beep(1200, 350)