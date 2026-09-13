param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"

# 1. Identificar origem e nome do projeto
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

# Caminho de destino sugerido por padrao
$destinoSugerido = if ($PastaDestino -ne "") { $PastaDestino } else { Join-Path $raiz "saida\$nomeAula" }

# =========================================================
# 2. DASHBOARD GRÁFICO UNIFICADO (WINDOWS FORMS PRO)
# =========================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "LUIS-MEDIA-TOOLS - Painel de Controle Pro"
$form.Size = New-Object System.Drawing.Size(520, 480)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 247, 250)

# Título do Topo
$lblHeader = New-Object System.Windows.Forms.Label
$lblHeader.Location = New-Object System.Drawing.Point(20, 15)
$lblHeader.Size = New-Object System.Drawing.Size(460, 30)
$lblHeader.Text = "CONFIGURAR ESTEIRA DE PRODUÇÃO"
$lblHeader.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$lblHeader.ForeColor = [System.Drawing.Color]::FromArgb(30, 41, 59)
$form.Controls.Add($lblHeader)

# Info da Aula/Origem
$lblOrigem = New-Object System.Windows.Forms.Label
$lblOrigem.Location = New-Object System.Drawing.Point(22, 48)
$lblOrigem.Size = New-Object System.Drawing.Size(460, 20)
$lblOrigem.Text = "Projeto: $nomeAula"
$lblOrigem.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$lblOrigem.ForeColor = [System.Drawing.Color]::FromArgb(71, 85, 105)
$form.Controls.Add($lblOrigem)

# Grupo: Pasta de Destino
$grpDestino = New-Object System.Windows.Forms.GroupBox
$grpDestino.Location = New-Object System.Drawing.Point(20, 75)
$grpDestino.Size = New-Object System.Drawing.Size(460, 70)
$grpDestino.Text = " Diretório de Destino "
$grpDestino.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($grpDestino)

$txtDestino = New-Object System.Windows.Forms.TextBox
$txtDestino.Location = New-Object System.Drawing.Point(15, 25)
$txtDestino.Size = New-Object System.Drawing.Size(335, 23)
$txtDestino.Text = $destinoSugerido
$grpDestino.Controls.Add($txtDestino)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Location = New-Object System.Drawing.Point(360, 24)
$btnBrowse.Size = New-Object System.Drawing.Size(85, 25)
$btnBrowse.Text = "Procurar..."
$btnBrowse.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.SelectedPath = $txtDestino.Text
    $dlg.Description = "Selecione o destino da aula:"
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $txtDestino.Text = $dlg.SelectedPath
    }
})
$grpDestino.Controls.Add($btnBrowse)

# Grupo: Módulos de Processamento
$grpModulos = New-Object System.Windows.Forms.GroupBox
$grpModulos.Location = New-Object System.Drawing.Point(20, 155)
$grpModulos.Size = New-Object System.Drawing.Size(460, 200)
$grpModulos.Text = " Selecione os Módulos Ativos "
$grpModulos.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($grpModulos)

# Checkbox 1: Auto-Cut
$chkAutoCut = New-Object System.Windows.Forms.CheckBox
$chkAutoCut.Location = New-Object System.Drawing.Point(20, 25)
$chkAutoCut.Size = New-Object System.Drawing.Size(420, 32)
$chkAutoCut.Text = "Auto-Cut Dinâmico (Remove silêncios + Timeline EDL DaVinci)"
$chkAutoCut.Checked = $true
$chkAutoCut.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$grpModulos.Controls.Add($chkAutoCut)

# Checkbox 2: Hardsub
$chkHardsub = New-Object System.Windows.Forms.CheckBox
$chkHardsub.Location = New-Object System.Drawing.Point(20, 65)
$chkHardsub.Size = New-Object System.Drawing.Size(420, 32)
$chkHardsub.Text = "Hardsub (Renderizar versão com legenda embutida no vídeo)"
$chkHardsub.Checked = $true
$chkHardsub.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$grpModulos.Controls.Add($chkHardsub)

# Checkbox 3: Slides e Apostila PDF
$chkSlides = New-Object System.Windows.Forms.CheckBox
$chkSlides.Location = New-Object System.Drawing.Point(20, 105)
$chkSlides.Size = New-Object System.Drawing.Size(420, 32)
$chkSlides.Text = "Slides Inteligentes e Apostila Oficial em PDF (Edge Headless)"
$chkSlides.Checked = $true
$chkSlides.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$grpModulos.Controls.Add($chkSlides)

# Checkbox 4: IA Local Llama
$chkIA = New-Object System.Windows.Forms.CheckBox
$chkIA.Location = New-Object System.Drawing.Point(20, 145)
$chkIA.Size = New-Object System.Drawing.Size(420, 32)
$chkIA.Text = "IA Local Llama (Resumo Executivo .md + Quiz Interativo .html)"
$chkIA.Checked = $true
$chkIA.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Regular)
$grpModulos.Controls.Add($chkIA)

# Vinculo: Se desligar o AutoCut, avisa/desmarca o Hardsub dependente
$chkAutoCut.Add_CheckedChanged({
    if (-not $chkAutoCut.Checked) {
        $chkHardsub.Checked = $false
        $chkHardsub.Enabled = $false
    } else {
        $chkHardsub.Enabled = $true
    }
})

# Botão Iniciar
$btnIniciar = New-Object System.Windows.Forms.Button
$btnIniciar.Location = New-Object System.Drawing.Point(260, 375)
$btnIniciar.Size = New-Object System.Drawing.Size(220, 42)
$btnIniciar.Text = "▶ INICIAR PROCESSAMENTO"
$btnIniciar.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnIniciar.ForeColor = [System.Drawing.Color]::White
$btnIniciar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnIniciar.FlatAppearance.BorderSize = 0
$btnIniciar.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($btnIniciar)

# Botão Cancelar
$btnCancelar = New-Object System.Windows.Forms.Button
$btnCancelar.Location = New-Object System.Drawing.Point(145, 375)
$btnCancelar.Size = New-Object System.Drawing.Size(100, 42)
$btnCancelar.Text = "Cancelar"
$btnCancelar.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnCancelar.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($btnCancelar)

$form.AcceptButton = $btnIniciar
$form.CancelButton = $btnCancelar

# Exibir janela
$resultadoJanela = $form.ShowDialog()

if ($resultadoJanela -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "[CANCELADO] Processamento cancelado pelo usuario." -ForegroundColor Yellow
    exit 0
}

# Capturar escolhas do usuário
$dirSaida     = $txtDestino.Text.Trim()
$fazerAutoCut = $chkAutoCut.Checked
$fazerHardsub = $chkHardsub.Checked
$fazerSlides  = $chkSlides.Checked
$fazerIA      = $chkIA.Checked

if (-not (Test-Path $dirSaida)) {
    New-Item -ItemType Directory -Path $dirSaida -Force | Out-Null
}

# 3. Estrutura técnica de entregáveis
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

# 4. Localizar vídeos brutos
$videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
if ($videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirSaida -Include "*.mp4","*.mkv","*.mov" | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
    if ($videos.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Nenhum video compativel encontrado.", "Aviso", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        exit 0
    }
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: PROCESSAMENTO EM EXECUÇÃO           " -ForegroundColor Cyan
Write-Host "   Projeto:      $nomeAula                               " -ForegroundColor Cyan
Write-Host "   Origem:       $dirEntrada                             " -ForegroundColor Cyan
Write-Host "   Destino:      $dirSaida                               " -ForegroundColor Cyan
Write-Host "   Auto-Cut:     $(if($fazerAutoCut){'ATIVO'}else{'DESATIVADO'})" -ForegroundColor Cyan
Write-Host "   Hardsub:      $(if($fazerHardsub){'ATIVO'}else{'DESATIVADO'})" -ForegroundColor Cyan
Write-Host "   Slides/PDF:   $(if($fazerSlides){'ATIVO'}else{'DESATIVADO'})"  -ForegroundColor Cyan
Write-Host "   IA Local:     $(if($fazerIA){'ATIVO'}else{'DESATIVADO'})"      -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# 5. Processamento por vídeo
$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # Auto-Cut com transição suave anti-estalo
    $videoAlvo = $video.FullName
    if ($fazerAutoCut) {
        $videoDinamico = Join-Path $dirSaida "${nome}_DINAMICO.mp4"
        if (-not (Test-Path $videoDinamico)) {
            Write-Host "    Fatiando pausas e gerando EDL..." -ForegroundColor DarkYellow
            & python (Join-Path $raiz "autocut_engine.py") $video.FullName $dirSaida
            Get-ChildItem -Path $dirSaida -Filter "${nome}_timeline_cortes.edl" | Move-Item -Destination $pastas["7"] -Force -ErrorAction SilentlyContinue
        }
        if (Test-Path $videoDinamico) { $videoAlvo = $videoDinamico }
    }

    # Minutagem contínua precisa
    $duracaoStr = (& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $videoAlvo)
    $duracao = 0.0
    [double]::TryParse($duracaoStr, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$duracao) | Out-Null
    $horas = [math]::Floor($tempoAcumulado / 3600)
    $minutos = [math]::Floor(($tempoAcumulado % 3600) / 60)
    $segundos = [math]::Floor($tempoAcumulado % 60)
    $stamp = if ($horas -gt 0) { "{0:D2}:{1:D2}:{2:D2}" -f [int]$horas, [int]$minutos, [int]$segundos } else { "{0:D2}:{1:D2}" -f [int]$minutos, [int]$segundos }
    $listaCapitulos += "$stamp - $nome"
    $tempoAcumulado += $duracao

    # Extrair Áudio Bruto (16kHz mono)
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp
    }

    # Tratamento Profissional Broadcast (EBU R128 + Highpass 80Hz)
    $audioTratTemp = Join-Path $dirTempChunk "$($nome)_tratado.wav"
    if (-not (Test-Path $audioTratTemp)) {
        Write-Host "    Tratando audio (EBU R128)..." -ForegroundColor DarkCyan
        & ffmpeg -hide_banner -loglevel error -y -i $audioBrutoTemp -af "highpass=f=80,loudnorm=I=-16:LRA=11:TP=-1.5" $audioTratTemp
    }

    # Transcrição via faster-whisper otimizada para Ryzen CPU
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

    # Renderização da versão Hardsub (se selecionado)
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

    # Copiar para pastas técnicas
    if (Test-Path $srtTemp) { Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force }
    if (Test-Path $audioBrutoTemp) { Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force }
    if (Test-Path $audioTratTemp) { Copy-Item -Path $audioTratTemp -Destination $pastas["3"] -Force }
}

$listaCapitulos | Out-File -FilePath $minutagemArquivo -Encoding UTF8
Write-Host "`n[OK] Minutagem gerada em: $minutagemArquivo" -ForegroundColor Cyan

# 6. Slides e Apostila PDF (se ativado)
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

# 7. IA Local Llama (se ativado)
if ($fazerIA -and (Test-Path (Join-Path $raiz "gerador_ia.py"))) {
    Write-Host "`n>>> [IA LOCAL - LLAMA] Criando Resumo e Quiz..." -ForegroundColor Magenta
    & python (Join-Path $raiz "gerador_ia.py") $dirSaida
}

# 8. Limpeza de subpastas intermediárias
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" -or $_.Name -match "^Aula\d+-\d+" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 9. Empacotamento
Write-Host "`n>>> [EMPACOTAMENTO] Compactando arquivos tecnicos no ZIP..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"], $pastas["7"] -DestinationPath $arquivoZip -Force

# 10. Limpeza de pastas intermediárias para poupar o SSD
if ((Test-Path $arquivoZip) -and ((Get-Item $arquivoZip).Length -gt 1024)) {
    foreach ($p in $pastas.Values) {
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

# 11. Mover vídeo bruto original para a raiz do destino
foreach ($video in $videos) {
    if ($video.DirectoryName -ne $dirSaida) {
        $destinoFinalVideo = Join-Path $dirSaida $video.Name
        Move-Item -LiteralPath $video.FullName -Destination $destinoFinalVideo -Force
    }
}

# 12. Limpar pasta de origem se ficou vazia
if ((Test-Path $dirEntrada) -and ($dirEntrada -ne $dirSaida) -and ($dirEntrada -ne $raiz)) {
    $itensRestantes = Get-ChildItem -Path $dirEntrada -Force
    if ($itensRestantes.Count -eq 0) {
        Remove-Item -LiteralPath $dirEntrada -Force -ErrorAction SilentlyContinue
    }
}

# 13. Alertas e Abertura
[System.Console]::Beep(1000, 300)
[System.Console]::Beep(1500, 400)
try {
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = "LUIS-MEDIA-TOOLS Concluido!"
    $notify.BalloonTipText = "Projeto [$nomeAula] finalizado com sucesso."
    $notify.Visible = $true
    $notify.ShowBalloonTip(4000)
} catch {}

explorer.exe $dirSaida

Write-Host "`n=========================================================" -ForegroundColor Green
Write-Host "   PIPELINE FINALIZADO COM SUCESSO!                     " -ForegroundColor Green
Write-Host "   Local:      $dirSaida                                " -ForegroundColor Green
Write-Host "   Entregavel: $arquivoZip                              " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
