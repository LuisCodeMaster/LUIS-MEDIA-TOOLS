param(
    [Parameter(Mandatory=$false)]
    [string]$CaminhoAula
)

$ErrorActionPreference = "Stop"
$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSaida = Join-Path $PastaScript "saida"

function Converter-SrtParaAss {
    param(
        [string]$ArquivoSrt,
        [string]$ArquivoAss
    )
    
    if (-not (Test-Path $ArquivoSrt)) { return }

    $cabecalhoAss = @"
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ShortsStyle,Montserrat,68,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,40,40,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"@
    
    $linhas = Get-Content -Path $ArquivoSrt -Encoding UTF8
    $eventos = @()
    $i = 0
    
    while ($i -lt $linhas.Count) {
        $linha = $linhas[$i].Trim()
        if ($linha -match '^\d+$') {
            $i++
            if ($i -ge $linhas.Count) { break }
            $tempoLinha = $linhas[$i].Trim()
            if ($tempoLinha -match '(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})') {
                $inicio = "$($Matches[1]):$($Matches[2]):$($Matches[3]).$([math]::Round([int]$Matches[4]/10).ToString('00'))"
                $fim = "$($Matches[5]):$($Matches[6]):$($Matches[7]).$([math]::Round([int]$Matches[8]/10).ToString('00'))"
                $i++
                $textoArray = @()
                while ($i -lt $linhas.Count -and -not [string]::IsNullOrWhiteSpace($linhas[$i])) {
                    $textoArray += $linhas[$i].Trim()
                    $i++
                }
                $textoAss = ($textoArray -join '\N') -replace '[\r\n]', ''
                $eventos += "Dialogue: 0,$inicio,$fim,ShortsStyle,,0,0,0,,{\b1}$textoAss{\b0}"
            }
        }
        $i++
    }
    
    $conteudoFinal = $cabecalhoAss + "`r`n" + ($eventos -join "`r`n")
    [System.IO.File]::WriteAllText($ArquivoAss, $conteudoFinal, [System.Text.UTF8Encoding]::new($false))
}

function Gerar-PacoteAula {
    param([string]$DiretorioAula)
    
    $NomeAula = [System.IO.Path]::GetFileName($DiretorioAula)
    Write-Host "Processando entregÃ¡veis de: $NomeAula" -ForegroundColor Cyan
    
    $dirLegendas = Join-Path $DiretorioAula "1_Legendas"
    $dirAudioTratado = Join-Path $DiretorioAula "3_Audio_Tratado"
    $dirDocs = Join-Path $DiretorioAula "6_Documentos"
    $dirWhisper = Join-Path $DiretorioAula "5_Dados_Whisper"
    
    if (-not (Test-Path $dirDocs)) { New-Item -ItemType Directory -Path $dirDocs -Force | Out-Null }
    
    # 1. Gerar legendas estilizadas .ASS para shorts
    if (Test-Path $dirLegendas) {
        $srts = Get-ChildItem -Path $dirLegendas -Filter "*shorts*.srt"
        foreach ($s in $srts) {
            $assOut = Join-Path $dirLegendas ($s.BaseName + ".ass")
            Converter-SrtParaAss -ArquivoSrt $s.FullName -ArquivoAss $assOut
        }
    }
    
    # 2. Varredura de metadados, contagem de palavras e duracoes
    $jsons = Get-ChildItem -Path $DiretorioAula -Recurse -Filter "*.json" | Sort-Object Name
    $duracaoTotalSegundos = 0.0
    $totalPalavras = 0
    $listaCapitulos = @()
    $tabelaBlocosMd = @("| Bloco | DuraÃ§Ã£o | Palavras | Ritmo (WPM) |", "|---|---|---|---|")
    $textoCompletoApostila = @("# Apostila DidÃ¡tica - $NomeAula`n`n")
    
    foreach ($j in $jsons) {
        $dados = Get-Content -Raw -Path $j.FullName -Encoding UTF8 | ConvertFrom-Json
        $nomeBloco = [System.IO.Path]::GetFileNameWithoutExtension($j.Name)
        
        $duracaoBloco = 0.0
        $palavrasBloco = 0
        $textoBloco = ""
        
        if ($dados.segments) {
            $primeiroSeg = $dados.segments[0].start
            $ultimoSeg = $dados.segments[-1].end
            $duracaoBloco = [double]$ultimoSeg
            
            foreach ($seg in $dados.segments) {
                $textoBloco += $seg.text + " "
            }
            $palavrasArray = ($textoBloco -split '\s+') | Where-Object { $_ -match '\w+' }
            $palavrasBloco = $palavrasArray.Count
        }
        
        # Timestamp de capitulo
        $tsObj = [timespan]::FromSeconds($duracaoTotalSegundos)
        $timestampFormatado = "{0:D2}:{1:D2}" -f [int]$tsObj.TotalMinutes, $tsObj.Seconds
        $listaCapitulos += "$timestampFormatado - $nomeBloco"
        
        # WPM (Words per minute)
        $minutos = if ($duracaoBloco -gt 0) { $duracaoBloco / 60.0 } else { 1.0 }
        $wpm = [int]($palavrasBloco / $minutos)
        
        $durStr = "{0:D2}:{1:D2}" -f [int]([timespan]::FromSeconds($duracaoBloco)).TotalMinutes, ([timespan]::FromSeconds($duracaoBloco)).Seconds
        $tabelaBlocosMd += "| $nomeBloco | $durStr | $palavrasBloco | $wpm WPM |"
        
        $textoCompletoApostila += "### $nomeBloco`n`n$($textoBloco.Trim())`n`n---`n"
        
        $duracaoTotalSegundos += $duracaoBloco
        $totalPalavras += $palavrasBloco
    }
    
    # Salvar Capitulos
    $caminhoCapitulos = Join-Path $dirDocs "capitulos-youtube.txt"
    [System.IO.File]::WriteAllLines($caminhoCapitulos, [string[]]$listaCapitulos, [System.Text.UTF8Encoding]::new($false))
    
    # Salvar Apostila
    $caminhoApostila = Join-Path $dirDocs "apostila-leitura.md"
    [System.IO.File]::WriteAllLines($caminhoApostila, [string[]]$textoCompletoApostila, [System.Text.UTF8Encoding]::new($false))
    
    # 3. Gerar RelatÃ³rio Executivo
    $durTotalObj = [timespan]::FromSeconds($duracaoTotalSegundos)
    $duracaoTotalFormatada = "{0:D2}h {1:D2}m {2:D2}s" -f $durTotalObj.Hours, $durTotalObj.Minutes, $durTotalObj.Seconds
    $wpmMedio = if ($durTotalObj.TotalMinutes -gt 0) { [int]($totalPalavras / $durTotalObj.TotalMinutes) } else { 0 }
    
    $relatorioMd = @"
# RelatÃ³rio de ProduÃ§Ã£o â€” $NomeAula

- **DuraÃ§Ã£o Total Consolidada:** $duracaoTotalFormatada
- **Total de Palavras Transcritas:** $totalPalavras palavras
- **Ritmo MÃ©dio de LocuÃ§Ã£o:** $wpmMedio WPM (Palavras Por Minuto)
- **Total de Blocos Processados:** $($jsons.Count) vÃ­deos

## Detalhamento por Bloco

$($tabelaBlocosMd -join "`r`n")

---
*Gerado automaticamente pelo LUIS MEDIA TOOLS*
"@
    $caminhoRelatorio = Join-Path $dirDocs "relatorio.md"
    [System.IO.File]::WriteAllText($caminhoRelatorio, $relatorioMd, [System.Text.UTF8Encoding]::new($false))
    
    # 4. Empacotar EntregÃ¡vel em .ZIP
    $arquivoZip = Join-Path $DiretorioAula "$NomeAula-Entregavel.zip"
    if (Test-Path $arquivoZip) { Remove-Item -Path $arquivoZip -Force }
    
    $itensParaZip = @()
    if (Test-Path $dirLegendas) { $itensParaZip += $dirLegendas }
    if (Test-Path $dirAudioTratado) { $itensParaZip += $dirAudioTratado }
    if (Test-Path $dirDocs) { $itensParaZip += $dirDocs }
    
    if ($itensParaZip.Count -gt 0) {
        $tempZipFolder = Join-Path $DiretorioAula "_temp_zip"
        if (Test-Path $tempZipFolder) { Remove-Item -Path $tempZipFolder -Recurse -Force }
        New-Item -ItemType Directory -Path $tempZipFolder -Force | Out-Null
        
        foreach ($item in $itensParaZip) {
            Copy-Item -Path $item -Destination (Join-Path $tempZipFolder (Split-Path -Leaf $item)) -Recurse -Force
        }
        
        Compress-Archive -Path "$tempZipFolder\*" -DestinationPath $arquivoZip -Force
        Remove-Item -Path $tempZipFolder -Recurse -Force
    }
    
    Write-Host "[OK] EntregÃ¡veis, legendas .ASS, relatÃ³rio e ZIP criados em: $NomeAula" -ForegroundColor Green
}

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "        GERADOR DE ENTREGÃVEIS E PACOTE CLIENTE          " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

if (-not [string]::IsNullOrWhiteSpace($CaminhoAula) -and (Test-Path $CaminhoAula)) {
    Gerar-PacoteAula -DiretorioAula $CaminhoAula
    exit 0
}

$pastasAulas = Get-ChildItem -Path $PastaSaida -Directory | Where-Object {
    $_.Name -notmatch "1_Legendas|2_Audio_Bruto|3_Audio_Tratado|4_Audio_Unificado|5_Dados_Whisper|6_Documentos"
}

if ($pastasAulas.Count -eq 0) {
    # Caso a saida ja tenha os arquivos organizados na raiz de saida
    Gerar-PacoteAula -DiretorioAula $PastaSaida
} else {
    foreach ($p in $pastasAulas) {
        Gerar-PacoteAula -DiretorioAula $p.FullName
    }
}

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "          TODOS OS ENTREGÃVEIS FORAM CONCLUÃDOS!         " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
[System.Console]::Beep(1000, 200)
[System.Console]::Beep(1400, 300)