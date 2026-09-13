param(
    [Parameter(Mandatory=$false)]
    [string]$PastaAulaAlvo
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSaida = Join-Path $PastaScript "saida"

function Unificar-AudiosPasta {
    param([string]$CaminhoPasta)

    $NomePasta = [System.IO.Path]::GetFileName($CaminhoPasta)
    Write-Host "Verificando audios em: $NomePasta" -ForegroundColor Cyan

    # Procura audios .wav e .mp3 gerados na pasta
    $audios = Get-ChildItem -Path $CaminhoPasta -Recurse -File | Where-Object {
        $_.Extension.ToLower() -in @(".wav", ".mp3") -and $_.Name -notmatch "aula-completa"
    } | Sort-Object Name

    if ($audios.Count -le 1) {
        Write-Host "Poucos audios encontrados ($($audios.Count)). Nada para unificar em $NomePasta." -ForegroundColor DarkGray
        return
    }

    Write-Host "Encontrados $($audios.Count) arquivos para unificacao." -ForegroundColor Yellow

    # Cria arquivo de lista temporario para o FFmpeg
    $txtLista = Join-Path $CaminhoPasta "lista_ffmpeg_concat.txt"
    $linhas = $audios | ForEach-Object { "file '" + $_.FullName.Replace('\', '/') + "'" }
    [System.IO.File]::WriteAllLines($txtLista, $linhas, [System.Text.UTF8Encoding]::new($false))

    $SaidaWav = Join-Path $CaminhoPasta "aula-completa.wav"
    $SaidaMp3 = Join-Path $CaminhoPasta "aula-completa.mp3"

    Write-Host "Gerando Master WAV..." -ForegroundColor Cyan
    & ffmpeg -y -f concat -safe 0 -i "$txtLista" -c copy "$SaidaWav" -loglevel error

    Write-Host "Gerando versao de estudo MP3..." -ForegroundColor Cyan
    & ffmpeg -y -i "$SaidaWav" -vn -b:a 192k "$SaidaMp3" -loglevel error

    if (Test-Path $txtLista) {
        Remove-Item -Path $txtLista -Force
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Unificacao concluida com sucesso!" -ForegroundColor Green
        Write-Host "Arquivo Master WAV: $SaidaWav" -ForegroundColor DarkGray
        Write-Host "Arquivo MP3: $SaidaMp3" -ForegroundColor DarkGray
    } else {
        Write-Host "ERRO ao unificar audios via FFmpeg." -ForegroundColor Red
    }
}

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "        UNIFICADOR DE AUDIOS DA AULA (MASTER)            " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($PastaAulaAlvo) -and (Test-Path $PastaAulaAlvo)) {
    Unificar-AudiosPasta -CaminhoPasta $PastaAulaAlvo
    exit 0
}

# Se nao passou parametro, varre a pasta saida
$pastas = Get-ChildItem -Path $PastaSaida -Directory | Where-Object {
    $_.Name -notmatch "1_Legendas|2_Audio_Bruto|3_Audio_Tratado|4_Audio_Unificado|5_Dados_Whisper|6_Documentos"
}

if ($pastas.Count -eq 0) {
    Unificar-AudiosPasta -CaminhoPasta $PastaSaida
} else {
    foreach ($p in $pastas) {
        Unificar-AudiosPasta -CaminhoPasta $p.FullName
    }
}

Write-Host ""
Write-Host "Processo de unificacao finalizado." -ForegroundColor Green