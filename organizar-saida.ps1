param(
    [Parameter(Mandatory=$false)]
    [string]$PastaSaida = "saida"
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  ORGANIZACAO DA ESTRUTURA DE ARQUIVOS   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$aulas = Get-ChildItem -Path $PastaSaida -Directory -ErrorAction SilentlyContinue

if ($aulas.Count -eq 0) {
    Write-Host "[!] Nenhuma pasta de aula encontrada em: $PastaSaida" -ForegroundColor Yellow
    exit 0
}

foreach ($aula in $aulas) {
    $caminhoAula = $aula.FullName
    Write-Host "[*] Organizando aula: $($aula.Name)" -ForegroundColor Yellow

    $pastas = @("1_Legendas", "2_Audio_Bruto", "3_Audio_Tratado", "4_Slides_Extraidos", "5_Editorial")
    foreach ($p in $pastas) {
        $destino = Join-Path $caminhoAula $p
        if (-not (Test-Path $destino)) {
            New-Item -ItemType Directory -Path $destino -Force | Out-Null
        }
    }

    # 1. Legendas
    Get-ChildItem -Path $caminhoAula -File | Where-Object { $_.Extension -match '\.(srt|vtt|tsv|json|ass)$' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $caminhoAula "1_Legendas") -Force -ErrorAction SilentlyContinue
    }

    # 2. Audio Bruto
    Get-ChildItem -Path $caminhoAula -File | Where-Object { $_.Extension -eq '.wav' -and $_.Name -notmatch 'norm|completa|master' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $caminhoAula "2_Audio_Bruto") -Force -ErrorAction SilentlyContinue
    }

    # 3. Audio Tratado
    Get-ChildItem -Path $caminhoAula -File | Where-Object { $_.Name -match 'norm|completa|master' -and $_.Extension -match '\.(wav|mp3)$' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $caminhoAula "3_Audio_Tratado") -Force -ErrorAction SilentlyContinue
    }

    # 4. Slides Extraidos
    Get-ChildItem -Path $caminhoAula -File | Where-Object { $_.Extension -match '\.(jpg|jpeg|png)$' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $caminhoAula "4_Slides_Extraidos") -Force -ErrorAction SilentlyContinue
    }

    # 5. Editorial
    Get-ChildItem -Path $caminhoAula -File | Where-Object { $_.Extension -match '\.(html|txt|md)$' } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination (Join-Path $caminhoAula "5_Editorial") -Force -ErrorAction SilentlyContinue
    }

    Write-Host "[OK] Pasta $($aula.Name) organizada!" -ForegroundColor Green
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Organizacao concluida com sucesso!" -ForegroundColor Green