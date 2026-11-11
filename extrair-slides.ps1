param(
    [Parameter(Mandatory=$false)]
    [string]$PastaAulaAlvo
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaEntrada = Join-Path $PastaScript "entrada"
$PastaSaida = Join-Path $PastaScript "saida"

function Processar-ExtracaoVideo {
    param([string]$CaminhoPasta)

    $nomeAula = [System.IO.Path]::GetFileName($CaminhoPasta)
    Write-Host "Processando Cérebro Editorial para: $nomeAula" -ForegroundColor Cyan

    $pastaDocs = Join-Path $CaminhoPasta "6_Documentos"
    $pastaImagens = Join-Path $pastaDocs "slides_extraidos"

    if (-not (Test-Path $pastaImagens)) {
        New-Item -ItemType Directory -Path $pastaImagens -Force | Out-Null
    }

    Get-ChildItem -Path $pastaImagens -File | Remove-Item -Force -ErrorAction SilentlyContinue

    $videos = Get-ChildItem -Path $PastaEntrada -Recurse -File | Where-Object {
        $_.Extension.ToLower() -in @(".mp4", ".mkv", ".mov", ".webm") -and $_.BaseName -eq $nomeAula
    }

    if ($videos.Count -eq 0) {
        $videos = Get-ChildItem -Path $PastaEntrada -Recurse -File | Where-Object {
            $_.Extension.ToLower() -in @(".mp4", ".mkv", ".mov", ".webm") -and $_.BaseName -like "*$nomeAula*"
        }
    }

    if ($videos.Count -gt 0) {
        $videoAlvo = $videos[0].FullName
        Write-Host "Extraindo frames de: $($videos[0].Name)" -ForegroundColor Yellow

        $saidaPattern = Join-Path $pastaImagens "frame_%04d.png"

        # Captura o frame 0 (inicio) ou qualquer variacao superior a 0.08
        & ffmpeg -y -i "$videoAlvo" -vf "select='eq(n\,0)+gt(scene\,0.08)',scale=1280:-1" -fps_mode vfr "$saidaPattern" -loglevel error

        $frames = Get-ChildItem -Path $pastaImagens -File
        
        # Fallback se a aula tiver variacao muito sutil: extrai 1 frame a cada 45 segundos
        if ($frames.Count -le 1) {
            Write-Host "Poucas mudancas bruscas detectadas. Aplicando amostragem regular..." -ForegroundColor DarkGray
            & ffmpeg -y -i "$videoAlvo" -vf "fps=1/45,scale=1280:-1" "$saidaPattern" -loglevel error
            $frames = Get-ChildItem -Path $pastaImagens -File
        }

        Write-Host "Frames capturados: $($frames.Count)" -ForegroundColor Green
    } else {
        Write-Host "[AVISO] Vídeo original não encontrado para $nomeAula em entrada/." -ForegroundColor DarkGray
    }

    python (Join-Path $PastaScript "editorial_engine.py") "$CaminhoPasta"
}

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "          CÉREBRO EDITORIAL: EXTRAÇÃO E APOSTILA         " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($PastaAulaAlvo) -and (Test-Path $PastaAulaAlvo)) {
    Processar-ExtracaoVideo -CaminhoPasta $PastaAulaAlvo
    exit 0
}

$pastas = Get-ChildItem -Path $PastaSaida -Directory | Where-Object {
    $_.Name -notmatch "1_Legendas|2_Audio_Bruto|3_Audio_Tratado|4_Audio_Unificado|5_Dados_Whisper|6_Documentos"
}

if ($pastas.Count -eq 0) {
    Processar-ExtracaoVideo -CaminhoPasta $PastaSaida
} else {
    foreach ($p in $pastas) {
        Processar-ExtracaoVideo -CaminhoPasta $p.FullName
    }
}

Write-Host ""
Write-Host "[OK] Processamento editorial concluído!" -ForegroundColor Green