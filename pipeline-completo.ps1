param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"
$configFile = Join-Path $raiz "config_presets.json"

$cfg = @{
    PresetIndex = 0; AutoCut = $true; EDL = $true; Hardsub = $true
    Slides = $true; PDF = $true; IA = $true; Resumo = $true; Quiz = $true; Cortes = $true; QtdCortes = 3
}

if (Test-Path $configFile) {
    try {
        $jsonContent = Get-Content $configFile -Raw | ConvertFrom-Json
        if ($jsonContent) { foreach ($key in $jsonContent.psobject.properties.name) { $cfg[$key] = $jsonContent.$key } }
    } catch {}
}

if ($CaminhoPasta -ne "") {
    $itemAlvo = Get-Item -LiteralPath $CaminhoPasta
    if ($itemAlvo.PSIsContainer) { $dirEntrada = $itemAlvo.FullName; $nomeAula = $itemAlvo.Name }
    else { $dirEntrada = $itemAlvo.DirectoryName; $nomeAula = (Get-Item $dirEntrada).Name }
} else {
    if ($Aula -eq "") { $Aula = "Aula1" }
    $nomeAula = $Aula; $dirEntrada = Join-Path $raiz "entrada\$nomeAula"
}

if (-not (Test-Path $dirEntrada)) {
    [System.Windows.Forms.MessageBox]::Show("Pasta de entrada nao encontrada:`n$dirEntrada", "Erro", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    exit 1
}

$destinoSugerido = if ($PastaDestino -ne "") { $PastaDestino } else { Join-Path $raiz "saida\$nomeAula" }

# =========================================================
# STUDIO HUB GUI
# =========================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "LUIS-MEDIA-TOOLS — Production Studio Hub"
$form.Size = New-Object System.Drawing.Size(620, 640)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

$pnlHeader = New-Object System.Windows.Forms.Panel
$pnlHeader.Location = New-Object System.Drawing.Point(0, 0); $pnlHeader.Size = New-Object System.Drawing.Size(620, 65)
$pnlHeader.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$form.Controls.Add($pnlHeader)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Location = New-Object System.Drawing.Point(20, 12); $lblTitle.Size = New-Object System.Drawing.Size(560, 24)
$lblTitle.Text = "ESTEIRA DE PÓS-PRODUÇÃO INTELIGENTE"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::White
$pnlHeader.Controls.Add($lblTitle)

$lblSubtitle = New-Object System.Windows.Forms.Label
$lblSubtitle.Location = New-Object System.Drawing.Point(22, 38); $lblSubtitle.Size = New-Object System.Drawing.Size(560, 18)
$lblSubtitle.Text = "Projeto: $nomeAula  |  Origem: $dirEntrada"
$lblSubtitle.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblSubtitle.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$pnlHeader.Controls.Add($lblSubtitle)

$lblDestino = New-Object System.Windows.Forms.Label
$lblDestino.Location = New-Object System.Drawing.Point(20, 78); $lblDestino.Size = New-Object System.Drawing.Size(120, 18)
$lblDestino.Text = "Pasta de Destino:"
$lblDestino.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($lblDestino)

$txtDestino = New-Object System.Windows.Forms.TextBox
$txtDestino.Location = New-Object System.Drawing.Point(20, 98); $txtDestino.Size = New-Object System.Drawing.Size(465, 23)
$txtDestino.Text = $destinoSugerido; $txtDestino.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Controls.Add($txtDestino)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Location = New-Object System.Drawing.Point(495, 96); $btnBrowse.Size = New-Object System.Drawing.Size(90, 27)
$btnBrowse.Text = "Procurar..."
$btnBrowse.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.SelectedPath = $txtDestino.Text
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { $txtDestino.Text = $dlg.SelectedPath }
})
$form.Controls.Add($btnBrowse)

$grpPreset = New-Object System.Windows.Forms.GroupBox
$grpPreset.Location = New-Object System.Drawing.Point(20, 135); $grpPreset.Size = New-Object System.Drawing.Size(565, 68)
$grpPreset.Text = " 1. Modo de Operação (Preset Guiado) "
$grpPreset.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($grpPreset)

$cmbPresets = New-Object System.Windows.Forms.ComboBox
$cmbPresets.Location = New-Object System.Drawing.Point(18, 26); $cmbPresets.Size = New-Object System.Drawing.Size(320, 24)
$cmbPresets.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$cmbPresets.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$cmbPresets.Items.AddRange(@("🎓 Curso Completo (Tudo Ativado)", "📱 Foco em Redes (Cortes 9:16 + Hardsub)", "🎬 Pré-Edição NLE (Apenas Auto-Cut + Timeline EDL)", "🛠 Personalizado"))
$cmbPresets.SelectedIndex = $cfg.PresetIndex
$grpPreset.Controls.Add($cmbPresets)

$lblPresetDesc = New-Object System.Windows.Forms.Label
$lblPresetDesc.Location = New-Object System.Drawing.Point(350, 25); $lblPresetDesc.Size = New-Object System.Drawing.Size(200, 32)
$lblPresetDesc.Text = "Voz Broadcast + Legenda Fluida para Aulas."
$lblPresetDesc.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Italic)
$lblPresetDesc.ForeColor = [System.Drawing.Color]::FromArgb(100, 116, 139)
$grpPreset.Controls.Add($lblPresetDesc)

$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Location = New-Object System.Drawing.Point(20, 215); $tabControl.Size = New-Object System.Drawing.Size(565, 290)
$tabControl.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($tabControl)

$tabVideo = New-Object System.Windows.Forms.TabPage
$tabVideo.Text = "Corte & Voz Pro"
$tabVideo.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabVideo)

$chkAutoCut = New-Object System.Windows.Forms.CheckBox
$chkAutoCut.Location = New-Object System.Drawing.Point(20, 18); $chkAutoCut.Size = New-Object System.Drawing.Size(510, 25)
$chkAutoCut.Text = "Ativar Auto-Cut Dinâmico (Fatiar pausas)"
$chkAutoCut.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkAutoCut.Checked = $cfg.AutoCut
$tabVideo.Controls.Add($chkAutoCut)

$chkEDL = New-Object System.Windows.Forms.CheckBox
$chkEDL.Location = New-Object System.Drawing.Point(40, 55); $chkEDL.Size = New-Object System.Drawing.Size(480, 24)
$chkEDL.Text = "Exportar Timeline EDL (DaVinci Resolve / Premiere)"
$chkEDL.Checked = $cfg.EDL
$tabVideo.Controls.Add($chkEDL)

$chkAudioBroadcast = New-Object System.Windows.Forms.CheckBox
$chkAudioBroadcast.Location = New-Object System.Drawing.Point(40, 85); $chkAudioBroadcast.Size = New-Object System.Drawing.Size(480, 24)
$chkAudioBroadcast.Text = "Masterização de Voz de Estúdio (Equalização + Compressor + R128)"
$chkAudioBroadcast.Checked = $true
$tabVideo.Controls.Add($chkAudioBroadcast)

$chkHardsubHoriz = New-Object System.Windows.Forms.CheckBox
$chkHardsubHoriz.Location = New-Object System.Drawing.Point(40, 115); $chkHardsubHoriz.Size = New-Object System.Drawing.Size(480, 24)
$chkHardsubHoriz.Text = "Gerar Versão Horizontal com Legenda Fluida na Borda"
$chkHardsubHoriz.Checked = $cfg.Hardsub
$tabVideo.Controls.Add($chkHardsubHoriz)

$tabDidatico = New-Object System.Windows.Forms.TabPage
$tabDidatico.Text = "Material & IA"
$tabDidatico.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabDidatico)

$chkSlides = New-Object System.Windows.Forms.CheckBox
$chkSlides.Location = New-Object System.Drawing.Point(20, 20); $chkSlides.Size = New-Object System.Drawing.Size(510, 25)
$chkSlides.Text = "Detecção Inteligente de Slides"
$chkSlides.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkSlides.Checked = $cfg.Slides
$tabDidatico.Controls.Add($chkSlides)

$chkPDF = New-Object System.Windows.Forms.CheckBox
$chkPDF.Location = New-Object System.Drawing.Point(40, 50); $chkPDF.Size = New-Object System.Drawing.Size(480, 24)
$chkPDF.Text = "Compilar Apostila Ilustrada em PDF"
$chkPDF.Checked = $cfg.PDF
$tabDidatico.Controls.Add($chkPDF)

$chkIA = New-Object System.Windows.Forms.CheckBox
$chkIA.Location = New-Object System.Drawing.Point(20, 95); $chkIA.Size = New-Object System.Drawing.Size(510, 25)
$chkIA.Text = "Processamento Cognitivo Local (Llama 3.2)"
$chkIA.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkIA.Checked = $cfg.IA
$tabDidatico.Controls.Add($chkIA)

$chkResumo = New-Object System.Windows.Forms.CheckBox
$chkResumo.Location = New-Object System.Drawing.Point(40, 125); $chkResumo.Size = New-Object System.Drawing.Size(480, 24)
$chkResumo.Text = "Gerar Resumo Executivo Estruturado"
$chkResumo.Checked = $cfg.Resumo
$tabDidatico.Controls.Add($chkResumo)

$chkQuiz = New-Object System.Windows.Forms.CheckBox
$chkQuiz.Location = New-Object System.Drawing.Point(40, 155); $chkQuiz.Size = New-Object System.Drawing.Size(480, 24)
$chkQuiz.Text = "Gerar Quiz Interativo de Fixação"
$chkQuiz.Checked = $cfg.Quiz
$tabDidatico.Controls.Add($chkQuiz)

$tabRedes = New-Object System.Windows.Forms.TabPage
$tabRedes.Text = "Redes Sociais (9:16)"
$tabRedes.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabRedes)

$chkCortes = New-Object System.Windows.Forms.CheckBox
$chkCortes.Location = New-Object System.Drawing.Point(20, 20); $chkCortes.Size = New-Object System.Drawing.Size(510, 25)
$chkCortes.Text = "Ativar Curadoria Viral e Cortes 9:16"
$chkCortes.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkCortes.Checked = $cfg.Cortes
$tabRedes.Controls.Add($chkCortes)

$cmbPresets.Add_SelectedIndexChanged({
    switch ($cmbPresets.SelectedIndex) {
        0 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $true; $chkPDF.Checked = $true; $chkIA.Checked = $true; $chkResumo.Checked = $true; $chkQuiz.Checked = $true; $chkCortes.Checked = $true }
        1 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $false; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $false; $chkPDF.Checked = $false; $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false; $chkCortes.Checked = $true }
        2 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $false; $chkSlides.Checked = $false; $chkPDF.Checked = $false; $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false; $chkCortes.Checked = $false }
    }
})

$btnIniciar = New-Object System.Windows.Forms.Button
$btnIniciar.Location = New-Object System.Drawing.Point(345, 525); $btnIniciar.Size = New-Object System.Drawing.Size(240, 48)
$btnIniciar.Text = "▶ INICIAR PROCESSAMENTO"
$btnIniciar.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnIniciar.ForeColor = [System.Drawing.Color]::White
$btnIniciar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnIniciar.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($btnIniciar)

$btnCancelar = New-Object System.Windows.Forms.Button
$btnCancelar.Location = New-Object System.Drawing.Point(220, 525); $btnCancelar.Size = New-Object System.Drawing.Size(115, 48)
$btnCancelar.Text = "Cancelar"
$btnCancelar.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnCancelar.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($btnCancelar)

$form.AcceptButton = $btnIniciar
$form.CancelButton = $btnCancelar

if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }

$novoCfg = [PSCustomObject]@{
    PresetIndex = $cmbPresets.SelectedIndex; AutoCut = $chkAutoCut.Checked; EDL = $chkEDL.Checked
    Hardsub = $chkHardsubHoriz.Checked; Slides = $chkSlides.Checked; PDF = $chkPDF.Checked
    IA = $chkIA.Checked; Resumo = $chkResumo.Checked; Quiz = $chkQuiz.Checked; Cortes = $chkCortes.Checked
}
$novoCfg | ConvertTo-Json | Set-Content -Path $configFile -Encoding UTF8

$dirSaida       = $txtDestino.Text.Trim()
$fazerAutoCut   = $chkAutoCut.Checked
$fazerEDL       = $chkEDL.Checked
$fazerHardsub   = $chkHardsubHoriz.Checked
$fazerSlides    = $chkSlides.Checked
$fazerPDF       = $chkPDF.Checked
$fazerIA        = $chkIA.Checked
$fazerCortes    = $chkCortes.Checked

if (-not (Test-Path $dirSaida)) { New-Item -ItemType Directory -Path $dirSaida -Force | Out-Null }

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

$videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
if ($videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirSaida -Include "*.mp4","*.mkv","*.mov" | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
    if ($videos.Count -eq 0) { exit 0 }
}

$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    $videoAlvo = $video.FullName
    if ($fazerAutoCut) {
        $videoDinamico = Join-Path $dirSaida "${nome}_DINAMICO.mp4"
        if (-not (Test-Path $videoDinamico)) {
            & python (Join-Path $raiz "autocut_engine.py") $video.FullName $dirSaida
            if ($fazerEDL) {
                Get-ChildItem -Path $dirSaida -Filter "${nome}_timeline_cortes.edl" | Move-Item -Destination $pastas["7"] -Force -ErrorAction SilentlyContinue
            }
        }
        if (Test-Path $videoDinamico) { $videoAlvo = $videoDinamico }
    }

    $duracaoStr = (& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $videoAlvo)
    $duracao = 0.0
    [double]::TryParse($duracaoStr, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$duracao) | Out-Null
    $horas = [math]::Floor($tempoAcumulado / 3600)
    $minutos = [math]::Floor(($tempoAcumulado % 3600) / 60)
    $segundos = [math]::Floor($tempoAcumulado % 60)
    $stamp = if ($horas -gt 0) { "{0:D2}:{1:D2}:{2:D2}" -f [int]$horas, [int]$minutos, [int]$segundos } else { "{0:D2}:{1:D2}" -f [int]$minutos, [int]$segundos }
    $listaCapitulos += "$stamp - $nome"
    $tempoAcumulado += $duracao

    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp

    $audioTratTemp = Join-Path $dirTempChunk "$($nome)_tratado.wav"
    $cadeiaFiltrosVoz = "highpass=f=80,equalizer=f=3000:width_type=o:w=2:g=3,compand=0.3|0.3:1|1:-90/-60|-60/-40|-40/-30:6:0:-90:0.1,loudnorm=I=-16:LRA=11:TP=-1.5"
    & ffmpeg -hide_banner -loglevel error -y -i $audioBrutoTemp -af $cadeiaFiltrosVoz $audioTratTemp

    $srtFinal = Join-Path $pastas["1"] "$nome.srt"
    $assFinal = Join-Path $pastas["1"] "$nome.ass"
    
    Write-Host "    Transcrevendo com Whisper (Word Timestamps) para Legenda Fluida..." -ForegroundColor Yellow
    $scriptTranscricao = @"
import os
try:
    from faster_whisper import WhisperModel
    model = WhisperModel('medium', device='cpu', compute_type='int8')
    segments, _ = model.transcribe(r'$audioBrutoTemp', language='pt', word_timestamps=True)
    
    with open(r'$srtFinal', 'w', encoding='utf-8') as f_srt, open(r'$assFinal', 'w', encoding='utf-8') as f_ass:
        # Cabecalho do formato ASS para gerenciar fade suave e elegancia na borda
        f_ass.write('[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n')
        f_ass.write('[V4+ Styles]\n')
        f_ass.write('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n')
        # Estilo Aula Fluida: Arial limpa, tamanho 54 (proporcional a 1080p), cor branca com sombra suave e fundo semitransparente discreto
        f_ass.write('Style: AulaFluida,Arial,54,&H00FFFFFF,&H0000FFFF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,1.5,1,2,40,40,35,1\n\n')
        f_ass.write('[Events]\n')
        f_ass.write('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')
        
        idx = 1
        for seg in segments:
            h1, m1, s1 = int(seg.start // 3600), int((seg.start % 3600) // 60), seg.start % 60
            h2, m2, s2 = int(seg.end // 3600), int((seg.end % 3600) // 60), seg.end % 60
            
            tc_srt1 = f'{h1:02d}:{m1:02d}:{s1:06.3f}'.replace('.', ',')
            tc_srt2 = f'{h2:02d}:{m2:02d}:{s2:06.3f}'.replace('.', ',')
            f_srt.write(f'{idx}\n{tc_srt1} --> {tc_srt2}\n{seg.text.strip()}\n\n')
            
            # Formato de tempo para ASS (H:MM:SS.cc)
            def fmt_ass(t):
                th = int(t // 3600)
                tm = int((t % 3600) // 60)
                ts = t % 60
                return f'{th}:{tm:02d}:{ts:05.2f}'
            
            t_start = fmt_ass(seg.start)
            t_end = fmt_ass(seg.end)
            texto_limpo = seg.text.strip().replace('\n', ' ')
            
            # Adiciona efeito imersivo de fade-in suave de 150ms na legenda da aula
            f_ass.write(f'Dialogue: 0,{t_start},{t_end},AulaFluida,,0,0,0,,{{\\fad(150,150)}}{texto_limpo}\n')
            idx += 1
            
    print('    [OK] Legendas SRT e ASS fluidas geradas com sucesso.')
except Exception as e:
    print(f'    [ERRO WHISPER] {e}')
"@
    python -c $scriptTranscricao
    Start-Sleep -Seconds 1

    # HARD SUB USANDO O ARQUIVO ASS FLUIDO (Com animação de fade suave e margem elegante)
    if ($fazerHardsub -and (Test-Path $assFinal) -and ((Get-Item $assFinal).Length -gt 10)) {
        $videoLegendado = Join-Path $dirSaida "${nome}_DINAMICO_LEGENDADO.mp4"
        if (-not (Test-Path $videoLegendado)) {
            Write-Host "    Renderizando versao com Legenda Fluida para Aulas..." -ForegroundColor Magenta
            $assFormatado = $assFinal.Replace("\", "/").Replace(":", "\:")
            
            & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo `
                -vf "subtitles='$assFormatado'" `
                -c:v libx264 -preset faster -crf 20 -c:a copy $videoLegendado
        }
    }

    if (Test-Path $audioBrutoTemp) { Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force }
    if (Test-Path $audioTratTemp) { Copy-Item -Path $audioTratTemp -Destination $pastas["3"] -Force }
}

$listaCapitulos | Out-File -FilePath $minutagemArquivo -Encoding UTF8

if ($fazerSlides) {
    foreach ($video in $videos) {
        $prefixo = $video.BaseName
        $padraoSaida = Join-Path $pastas["4"] "${prefixo}_slide_%03d.jpg"
        & ffmpeg -hide_banner -loglevel error -y -i $video.FullName -vf "select='gt(scene,0.25)',mpdecimate" -fps_mode vfr -q:v 2 $padraoSaida
    }
    if ($fazerPDF -and (Test-Path (Join-Path $raiz "editorial_engine.py"))) {
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

if ($fazerIA -and (Test-Path (Join-Path $raiz "gerador_ia.py"))) {
    & python (Join-Path $raiz "gerador_ia.py") $dirSaida
}

if ($fazerCortes -and (Test-Path (Join-Path $raiz "gerador_cortes.py"))) {
    & python (Join-Path $raiz "gerador_cortes.py") $dirSaida
}

Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" -or $_.Name -match "^Aula\d+-\d+" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"], $pastas["7"] -DestinationPath $arquivoZip -Force

if ((Test-Path $arquivoZip) -and ((Get-Item $arquivoZip).Length -gt 1024)) {
    foreach ($p in $pastas.Values) {
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

foreach ($video in $videos) {
    if ($video.DirectoryName -ne $dirSaida) {
        Move-Item -LiteralPath $video.FullName -Destination (Join-Path $dirSaida $video.Name) -Force
    }
}

[System.Console]::Beep(1000, 300)
[System.Console]::Beep(1500, 400)
explorer.exe $dirSaida
