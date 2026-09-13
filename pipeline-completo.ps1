param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"

# Função auxiliar para janelas de Sim/Não
function Perguntar-Opcao {
    param([string]$Mensagem, [string]$Titulo)
    $res = [System.Windows.Forms.MessageBox]::Show($Mensagem, $Titulo, [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Question)
    return ($res -eq [System.Windows.Forms.DialogResult]::Yes)
}

# 1. Identificar origem e projeto
if ($CaminhoPasta -ne "") {
    $itemAlvo = Get-Item -LiteralPath $CaminhoPasta
    if ($itemAlvo.PSIsContainer) {
        $dirEntrada = $itemAlvo.FullName
        $nomeAula   = $itemAlvo.Name
    } else {
        $dirEntrada = $itemAlvo.DirectoryName
        $nomeAula   = (Get-Item $dirEntrada).Name
    }
} else {
    if ($Aula -eq "") { $Aula = "Aula1" }
    $nomeAula   = $Aula
    $dirEntrada = Join-Path $raiz "entrada\$nomeAula"
}

if (-not (Test-Path $dirEntrada)) {
    [System.Windows.Forms.MessageBox]::Show("Pasta de entrada nao encontrada: $dirEntrada", "Erro", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    exit 1
}

# 2. JANELA 1: Selecionar Destino
$saidaPadrao = Join-Path $raiz "saida\$nomeAula"
if ($PastaDestino -eq "") {
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "LUIS-MEDIA-TOOLS`nSelecione onde salvar o projeto final [$nomeAula]:"
    $dialog.SelectedPath = (Join-Path $raiz "saida")
    $dialog.ShowNewFolderButton = $true

    $resultado = $dialog.ShowDialog()

    if ($resultado -eq [System.Windows.Forms.DialogResult]::OK -and (-not [string]::IsNullOrWhiteSpace($dialog.SelectedPath))) {
        if ($dialog.SelectedPath -match "saida$") {
            $dirSaida = Join-Path $dialog.SelectedPath $nomeAula
        } else {
            $dirSaida = $dialog.SelectedPath
        }
    } else {
        $dirSaida = $saidaPadrao
    }
} else {
    $dirSaida = $PastaDestino
}

if (-not (Test-Path $dirSaida)) {
    New-Item -ItemType Directory -Path $dirSaida -Force | Out-Null
}

# 3. JANELAS DE INTERAÇÃO COM O USUÁRIO
$fazerAutoCut = Perguntar-Opcao "Deseja ativar o AUTO-CUT?`n`n- Remove pausas de respiracao e momentos mortos`n- Gera video DINAMICO fluido (sem estalos)`n- Exporta linha do tempo .EDL para Premiere/DaVinci" "Opcao 1: Remocao de Silencio"

$fazerHardsub = $false
if ($fazerAutoCut) {
    $fazerHardsub = Perguntar-Opcao "Deseja gerar tambem uma versao com LEGENDA EMBUTIDA no video?`n`nIdeal para postar no Reels, TikTok, Shorts ou consumo direto no celular." "Opcao 2: Hardsub (Video Legendado)"
}

$fazerSlides = Perguntar-Opcao "Deseja fazer a DETECCAO INTELIGENTE DE SLIDES e criar a APOSTILA EM PDF?`n`nExtrai imagens apenas quando houver troca real de cena na tela." "Opcao 3: Slides e Apostila Didatica"

$fazerIA = Perguntar-Opcao "Deseja acionar a IA LOCAL (Llama)?`n`n- Cria Resumo Executivo em Markdown`n- Cria Quiz Interativo em HTML com gabarito" "Opcao 4: IA Pedagogica"

# 4. Estrutura de entregaveis
$pastas = @{
    "1" = Join-Path $dirSaida "1_Legendas"
    "2" = Join-Path $dirSaida "2_Audio_Bruto"
    "3" = Join-Path $dirSaida "3_Audio_Tratado"
    "4" = Join-Path $dirSaida "4_Slides_Extraidos"
    "5" = Join-Path $dirSaida "5_Editorial"
    "6" = Join-Path $dirSaida "6_Documentos"
    "7" = Join-Path $dirSaida "7_Cortes_Timeline"
}

foreach ($p in $pastas.Values) {
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# 5. Localizar videos brutos
$videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
if ($videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirSaida -Include "*.mp4","*.mkv","*.mov" | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
    if ($videos.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Nenhum video compativel encontrado.", "Aviso", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        exit 0
    }
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: PROCESSAMENTO PERSONALIZADO         " -ForegroundColor Cyan
Write-Host "   Projeto:      $nomeAula                               " -ForegroundColor Cyan
Write-Host "   Auto-Cut:     $(if($fazerAutoCut){'SIM'}else{'NAO'})  " -ForegroundColor Cyan
Write-Host "   Hardsub:      $(if($fazerHardsub){'SIM'}else{'NAO'})  " -ForegroundColor Cyan
Write-Host "   Slides/PDF:   $(if($fazerSlides){'SIM'}else{'NAO'})   " -ForegroundColor Cyan
Write-Host "   IA Local:     $(if($fazerIA){'SIM'}else{'NAO'})       " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# 6. Processamento
$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # Auto-Cut
    $videoAlvo = $video.FullName
    if ($fazerAutoCut) {
        $videoDinamico = Join-Path $dirSaida "${nome}_DINAMICO.mp4"
        if (-not (Test-Path $videoDinamico)) {
            Write-Host "    Fatiando silencios e gerando EDL..." -ForegroundColor DarkYellow
            & python (Join-Path $raiz "autocut_engine.py") $video.FullName $dirSaida
            Get-ChildItem -Path $dirSaida -Filter "${nome}_timeline_cortes.edl" | Move-Item -Destination $pastas["7"] -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path $videoDinamico) { $videoAlvo = $videoDinamico }
    }

    # Minutagem
    $duracaoStr = (& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $videoAlvo)
    $duracao = 0.0
    [double]::TryParse($duracaoStr, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$duracao) | Out-Null
    $horas = [math]::Floor($tempoAcumulado / 3600)
    $minutos = [math]::Floor(($tempoAcumulado % 3600) / 60)
    $segundos = [math]::Floor($tempoAcumulado % 60)
    $stamp = if ($horas -gt 0) { "{0:D2}:{1:D2}:{2:D2}" -f [int]$horas, [int]$minutos, [int]$segundos } else { "{0:D2}:{1:D2}" -f [int]$minutos, [int]$segundos }
    $listaCapitulos += "$stamp - $nome"
    $tempoAcumulado += $duracao

    # Extrair Audio Bruto
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp
    }

    # Tratamento de Audio
    $audioTratTemp = Join-Path $dirTempChunk "$($nome)_tratado.wav"
    if (-not (Test-Path $audioTratTemp)) {
        Write-Host "    Tratando audio (EBU R128)..." -ForegroundColor DarkCyan
        & ffmpeg -hide_banner -loglevel error -y -i $audioBrutoTemp -af "highpass=f=80,loudnorm=I=-16:LRA=11:TP=-1.5" $audioTratTemp
    }

    # Whisper
    $srtTemp = Join-Path $dirTempChunk "$nome.srt"
    if (-not (Test-Path $srtTemp)) {
        Write-Host "    Transcrevendo com Whisper..." -ForegroundColor Yellow
        $scriptTranscricao = @"
import os, sys
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
try:
    from faster_whisper import WhisperModel
    model = WhisperModel('medium', device='cpu', compute_type='int8')
    segments, _ = model.transcribe(r'$audioBrutoTemp', language='pt')
    with open(r'$srtTemp', 'w', encoding='utf-8') as f:
        idx = 1
        for s in segments:
            h1, m1, s1 = int(s.start // 3600), int((s.start % 3600) // 60), s.start % 60
            h2, m2, s2 = int(s.end // 3600), int((s.end % 3600) // 60), s.end % 60
            f.write(f'{idx}\n{h1:02d}:{m1:02d}:{s1:06.3f}'.replace('.', ',') + ' --> ' + f'{h2:02d}:{m2:02d}:{s2:06.3f}'.replace('.', ',') + f'\n{s.text.strip()}\n\n')
            idx += 1
except Exception:
    import subprocess
    subprocess.run(['whisper', r'$audioBrutoTemp', '--model', 'medium', '--language', 'pt', '--output_dir', r'$dirTempChunk'])
"@
        python -c $scriptTranscricao
    }

    # Hardsub
    if ($fazerHardsub -and (Test-Path $srtTemp)) {
        $videoLegendado = Join-Path $dirSaida "${nome}_DINAMICO_LEGENDADO.mp4"
        if (-not (Test-Path $videoLegendado)) {
            Write-Host "    Renderizando Hardsub (legenda embutida)..." -ForegroundColor Magenta
            $srtFormatado = $srtTemp.Replace("\", "/").Replace(":", "\:")
            $estiloLegenda = "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,MarginV=25"
            & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo `
                -vf "subtitles='$srtFormatado':force_style='$estiloLegenda'" `
                -c:v libx264 -preset faster -crf 20 -c:a copy $videoLegendado
        }
    }

    # Copia itens para entregaveis
    if (Test-Path $srtTemp) { Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force }
    if (Test-Path $audioBrutoTemp) { Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force }
    if (Test-Path $audioTratTemp) { Copy-Item -Path $audioTratTemp -Destination $pastas["3"] -Force }
}

$listaCapitulos | Out-File -FilePath $minutagemArquivo -Encoding UTF8

# 7. Slides e Apostila (se ativado)
if ($fazerSlides) {
    Write-Host "`n>>> [SLIDES] Detectando trocas reais de cena..." -ForegroundColor Cyan
    foreach ($video in $videos) {
        $prefixo = $video.BaseName
        $padraoSaida = Join-Path $pastas["4"] "${prefixo}_slide_%03d.jpg"
        & ffmpeg -hide_banner -loglevel error -y -i $video.FullName `
            -vf "select='gt(scene,0.25)',mpdecimate" `
            -vsync vfr -q:v 2 $padraoSaida
        $gerados = Get-ChildItem -Path $pastas["4"] -Filter "${prefixo}_slide_*.jpg"
        if ($gerados.Count -eq 0) {
            $slideFallback = Join-Path $pastas["4"] "${prefixo}_slide_001.jpg"
            & ffmpeg -hide_banner -loglevel error -y -ss 00:00:05 -i $video.FullName -vframes 1 -q:v 2 $slideFallback
        }
    }

    if (Test-Path (Join-Path $raiz "editorial_engine.py")) {
        Write-Host ">>> [EDITORIAL] Gerando apostila e convertendo para PDF..." -ForegroundColor Cyan
        & python (Join-Path $raiz "editorial_engine.py") $dirSaida
        $apostilaHtml = Join-Path $pastas["6"] "apostila-ilustrada.html"
        if (Test-Path $apostilaHtml) {
            Copy-Item -Path $apostilaHtml -Destination $pastas["5"] -Force
            $edgePaths = @("C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", "C:\Program Files\Microsoft\Edge\Application\msedge.exe")
            $edgeExe = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
            if ($edgeExe) {
                $pdfDestino = Join-Path $pastas["6"] "Apostila-Oficial.pdf"
                & $edgeExe --headless --disable-gpu --print-to-pdf="$pdfDestino" "$apostilaHtml" 2>$null
            }
        }
    }
}

# 8. IA Local Llama (se ativado)
if ($fazerIA -and (Test-Path (Join-Path $raiz "gerador_ia.py"))) {
    Write-Host "`n>>> [IA LOCAL - LLAMA] Criando Resumo e Quiz..." -ForegroundColor Magenta
    & python (Join-Path $raiz "gerador_ia.py") $dirSaida
}

# 9. Limpeza de subpastas intermediarias
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" -or $_.Name -match "^Aula\d+-\d+" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 10. Empacotamento
Write-Host "`n>>> [EMPACOTAMENTO] Compactando dados tecnicos no ZIP..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"], $pastas["7"] -DestinationPath $arquivoZip -Force

# 11. Limpeza de pastas soltas (SSD protegido)
if ((Test-Path $arquivoZip) -and ((Get-Item $arquivoZip).Length -gt 1024)) {
    foreach ($p in $pastas.Values) {
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

# 12. Consolidar videos brutos na raiz do destino
foreach ($video in $videos) {
    if ($video.DirectoryName -ne $dirSaida) {
        $destinoFinalVideo = Join-Path $dirSaida $video.Name
        Move-Item -LiteralPath $video.FullName -Destination $destinoFinalVideo -Force
    }
}

# 13. Limpar pasta de origem vazia
if ((Test-Path $dirEntrada) -and ($dirEntrada -ne $dirSaida) -and ($dirEntrada -ne $raiz)) {
    $itensRestantes = Get-ChildItem -Path $dirEntrada -Force
    if ($itensRestantes.Count -eq 0) {
        Remove-Item -LiteralPath $dirEntrada -Force -ErrorAction SilentlyContinue
    }
}

# 14. Alertas e Abertura
[System.Console]::Beep(1000, 300)
[System.Console]::Beep(1500, 400)
[System.Windows.Forms.MessageBox]::Show("Projeto [$nomeAula] finalizado com sucesso!`n`nLocal: $dirSaida", "LUIS-MEDIA-TOOLS", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
explorer.exe $dirSaida
