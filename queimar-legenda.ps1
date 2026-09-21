param(
    [Parameter(Mandatory=$false)]
    [string]$ArquivoVideo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

function Queimar-LegendaArquivo {
    param(
        [string]$CaminhoVideo,
        [string]$TipoLegenda = "Shorts" # "Shorts" (.ass) ou "Padrao" (.srt)
    )

    $VideoFull = (Resolve-Path $CaminhoVideo).Path
    $NomeVideo = [System.IO.Path]::GetFileName($VideoFull)
    $NomeBase = [System.IO.Path]::GetFileNameWithoutExtension($VideoFull)
    
    # Localiza a legenda correspondente dentro da arvore de saida
    $arquivoLegenda = $null
    if ($TipoLegenda -eq "Shorts") {
        $arquivoLegenda = Get-ChildItem -Path $PastaSaida -Recurse -Filter "*$NomeBase*shorts*.ass" | Select-Object -First 1
        if (-not $arquivoLegenda) {
            $arquivoLegenda = Get-ChildItem -Path $PastaSaida -Recurse -Filter "*$NomeBase*shorts*.srt" | Select-Object -First 1
        }
    } else {
        $arquivoLegenda = Get-ChildItem -Path $PastaSaida -Recurse -Filter "*$NomeBase*curta*.srt" | Select-Object -First 1
        if (-not $arquivoLegenda) {
            $arquivoLegenda = Get-ChildItem -Path $PastaSaida -Recurse -Filter "*$NomeBase*.srt" | Select-Object -First 1
        }
    }

    if (-not $arquivoLegenda) {
        Write-Host "Nenhuma legenda encontrada para: $NomeVideo. Processe o lote primeiro." -ForegroundColor Yellow
        return
    }

    $PastaDestino = Split-Path -Parent $arquivoLegenda.FullName
    $Sufixo = if ($TipoLegenda -eq "Shorts") { "-legendado-shorts.mp4" } else { "-legendado.mp4" }
    $VideoFinal = Join-Path $PastaDestino "$NomeBase$Sufixo"

    Write-Host "--------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Gravando legenda em: $NomeVideo" -ForegroundColor Cyan
    Write-Host "Legenda utilizada  : $($arquivoLegenda.Name)" -ForegroundColor DarkGray
    Write-Host "Destino            : $VideoFinal" -ForegroundColor DarkGray
    Write-Host "--------------------------------------------------" -ForegroundColor Cyan

    # Formata caminho com escape para o filtro de legendas do FFmpeg
    $legendaFormatada = $arquivoLegenda.FullName.Replace('\', '/').Replace(':', '\:')

    if ($arquivoLegenda.Extension -eq ".ass") {
        $filtroV = "ass='$legendaFormatada'"
    } else {
        # SRT com estilo embutido na base
        $filtroV = "subtitles='$legendaFormatada':force_style='FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,MarginV=30'"
    }

    & ffmpeg -y -i "$VideoFull" -vf "$filtroV" -c:a copy -c:v h264_amf -quality balanced -rc cqp -qp_i 20 -qp_p 22 -pix_fmt yuv420p "$VideoFinal" -loglevel error

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERRO ao gravar legenda em: $NomeVideo" -ForegroundColor Red
        return
    }

    Write-Host "[OK] Video com legenda gravada gerado: $VideoFinal" -ForegroundColor Green
}

Clear-Host
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "   QUEIMAR LEGENDAS NO VÍDEO (HARDSUB)   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Escolha o estilo de vídeo para gerar:" -ForegroundColor White
Write-Host "  [1] Shorts / Reels / TikTok (Usa estilo .ASS amarelo/destacado)" -ForegroundColor Yellow
Write-Host "  [2] Aula Padrão / YouTube 16:9 (Legenda horizontal limpa)" -ForegroundColor Yellow
Write-Host "  [0] Cancelar" -ForegroundColor DarkGray
Write-Host ""

$estilo = Read-Host "Opcao [1, 2 ou 0]"
if ($estilo -eq "0") { exit 0 }
$tipo = if ($estilo -eq "1") { "Shorts" } else { "Padrao" }

$exts = @(".mp4", ".mkv", ".mov", ".webm")
$videos = Get-ChildItem -Path $PastaEntrada -Recurse -File | Where-Object { $exts -contains $_.Extension.ToLower() } | Sort-Object Name

if ($videos.Count -eq 0) {
    Write-Host "Nenhum video encontrado na pasta entrada/." -ForegroundColor Yellow
    exit 0
}

$idx = 1
$tot = $videos.Count
foreach ($v in $videos) {
    Write-Progress -Activity "Gravando legendas nos vídeos" -Status "Processando [$idx/$tot]: $($v.Name)" -PercentComplete ([int]((($idx-1)/$tot)*100))
    Queimar-LegendaArquivo -CaminhoVideo $v.FullName -TipoLegenda $tipo
    $idx++
}

Write-Progress -Activity "Gravando legendas nos vídeos" -Completed
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "       TODOS OS VÍDEOS FORAM GERADOS!     " -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
[System.Console]::Beep(1000, 250)