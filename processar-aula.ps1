param(
    [Parameter(Mandatory=$false)]
    [string]$Arquivo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

function Processar-ArquivoIndividual {
    param(
        [string]$CaminhoArquivo,
        [int]$Atual = 1,
        [int]$Total = 1
    )

    $ArquivoFull = (Resolve-Path $CaminhoArquivo).Path
    $NomeArquivo = [System.IO.Path]::GetFileName($ArquivoFull)
    $NomeBase = [System.IO.Path]::GetFileNameWithoutExtension($ArquivoFull)
    $PastaResultado = Join-Path $PastaSaida $NomeBase

    $pctLote = [int]((($Atual - 1) / $Total) * 100)
    $restantes = $Total - $Atual

    $host.UI.RawUI.WindowTitle = "[$Atual/$Total] Processando: $NomeArquivo"

    $statusMsg = "Video $Atual de $Total - $NomeArquivo ($restantes restantes)"

    Write-Progress -Activity "Processamento em Lote - LUIS MEDIA TOOLS" -Status $statusMsg -PercentComplete $pctLote -CurrentOperation "Transcrevendo e gerando legendas..."

    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host " [$Atual/$Total] Processando: $NomeArquivo" -ForegroundColor Cyan
    Write-Host " Faltam: $restantes video(s)" -ForegroundColor DarkGray
    Write-Host "==========================================" -ForegroundColor Cyan

    if (-not (Test-Path $PastaResultado)) {
        New-Item -ItemType Directory -Path $PastaResultado -Force | Out-Null
    }

    & "$PastaScript\transcrever.ps1" "$ArquivoFull"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO no processamento de $NomeArquivo." -ForegroundColor Red
        return
    }

    Write-Host "`n[OK] Concluido: $NomeBase" -ForegroundColor Green
    Write-Host "Pasta: $PastaResultado`n" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "        LUIS MEDIA TOOLS - AULAS" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($Arquivo)) {
    if (-not (Test-Path $Arquivo)) {
        Write-Host "ERRO: Arquivo nao encontrado: $Arquivo" -ForegroundColor Red
        exit 1
    }
    Processar-ArquivoIndividual -CaminhoArquivo $Arquivo -Atual 1 -Total 1
    Write-Progress -Activity "Processamento em Lote - LUIS MEDIA TOOLS" -Completed
} else {
    $exts = @(".mp4", ".mkv", ".mov", ".avi", ".webm")
    $arquivos = Get-ChildItem -Path $PastaEntrada -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name

    if ($null -eq $arquivos -or $arquivos.Count -eq 0) {
        Write-Host "Nenhum video encontrado na pasta: $PastaEntrada" -ForegroundColor Yellow
        exit 0
    }

    $total = $arquivos.Count
    Write-Host "Foram encontrados $total video(s) na pasta entrada.`n" -ForegroundColor Green

    $index = 1
    foreach ($vid in $arquivos) {
        Processar-ArquivoIndividual -CaminhoArquivo $vid.FullName -Atual $index -Total $total
        $index++
    }

    Write-Progress -Activity "Processamento em Lote - LUIS MEDIA TOOLS" -Status "Concluido!" -PercentComplete 100 -Completed
    $host.UI.RawUI.WindowTitle = "LUIS MEDIA TOOLS - Lote Concluido!"
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "       TODOS OS PROCESSOS FINALIZADOS!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

[System.Console]::Beep(800, 200)
[System.Console]::Beep(1200, 350)