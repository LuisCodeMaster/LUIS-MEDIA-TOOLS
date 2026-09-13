param(
    [Parameter(Mandatory=$false)]
    [string]$PastaEntrada = "saida",
    
    [Parameter(Mandatory=$false)]
    [string]$PastaDestino = "saida"
)

function Testar-Comando ($comando) {
    return [bool](Get-Command $comando -ErrorAction SilentlyContinue)
}

if (-not (Testar-Comando "ffmpeg")) {
    Write-Host "[ERRO] FFmpeg nao encontrado no sistema." -ForegroundColor Red
    exit 1
}

function Normalizar-Arquivo {
    param([string]$caminhoEntrada, [string]$caminhoSaida)
    
    Write-Host "[*] Normalizando: $(Split-Path $caminhoEntrada -Leaf)" -ForegroundColor Yellow
    
    $cmd = "ffmpeg -y -i `"$caminhoEntrada`" -af loudnorm=I=-14:LRA=11:TP=-1.5 -ar 48000 `"$caminhoSaida`""
    Invoke-Expression $cmd | Out-Null
    
    if (Test-Path $caminhoSaida) {
        Write-Host "[OK] Sucesso: $(Split-Path $caminhoSaida -Leaf)" -ForegroundColor Green
    } else {
        Write-Host "[FALHA] Nao foi possivel normalizar $caminhoEntrada" -ForegroundColor Red
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  NORMALIZACAO DE AUDIO (-14 LUFS)        " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$aulas = Get-ChildItem -Path $PastaEntrada -Directory -ErrorAction SilentlyContinue

if ($aulas.Count -gt 0) {
    foreach ($aula in $aulas) {
        $pastaTratado = Join-Path $aula.FullName "3_Audio_Tratado"
        if (-not (Test-Path $pastaTratado)) {
            New-Item -ItemType Directory -Path $pastaTratado -Force | Out-Null
        }
        
        $pastaBruto = Join-Path $aula.FullName "2_Audio_Bruto"
        $arquivos = @()
        if (Test-Path $pastaBruto) {
            $arquivos = Get-ChildItem -Path $pastaBruto -Filter "*.wav" -File
        }
        if ($arquivos.Count -eq 0) {
            $arquivos = Get-ChildItem -Path $aula.FullName -Filter "*.wav" -File | Where-Object { $_.Name -notmatch "normalizado|master|aula-completa" }
        }
        
        foreach ($arq in $arquivos) {
            $saida = Join-Path $pastaTratado ($arq.BaseName + "_norm.wav")
            Normalizar-Arquivo -caminhoEntrada $arq.FullName -caminhoSaida $saida
        }
        
        $masterWav = Join-Path $aula.FullName "aula-completa.wav"
        if (Test-Path $masterWav) {
            $masterTratado = Join-Path $aula.FullName "aula-completa_norm.wav"
            Normalizar-Arquivo -caminhoEntrada $masterWav -caminhoSaida $masterTratado
        }
    }
} else {
    $arquivos = Get-ChildItem -Path $PastaEntrada -Filter "*.wav" -File
    foreach ($arq in $arquivos) {
        $saida = Join-Path $PastaDestino ($arq.BaseName + "_norm.wav")
        Normalizar-Arquivo -caminhoEntrada $arq.FullName -caminhoSaida $saida
    }
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Processo de normalizacao concluido!" -ForegroundColor Green