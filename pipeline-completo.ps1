param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"

# 1. Identificar entrada e projeto
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
    [System.Windows.Forms.MessageBox]::Show("Pasta de entrada nao encontrada:`n$dirEntrada", "Erro de Entrada", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    exit 1
}

$destinoSugerido = if ($PastaDestino -ne "") { $PastaDestino } else { Join-Path $raiz "saida\$nomeAula" }

# =========================================================
# STUDIO HUB GUI - INTERFACE GUIADA POR ABAS E PRESETS
# =========================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "LUIS-MEDIA-TOOLS — Production Studio Hub"
$form.Size = New-Object System.Drawing.Size(620, 640)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)

# --- CABEÇALHO ---
$pnlHeader = New-Object System.Windows.Forms.Panel
$pnlHeader.Location = New-Object System.Drawing.Point(0, 0)
$pnlHeader.Size = New-Object System.Drawing.Size(620, 65)
$pnlHeader.BackColor = [System.Drawing.Color]::FromArgb(15, 23, 42)
$form.Controls.Add($pnlHeader)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Location = New-Object System.Drawing.Point(20, 12)
$lblTitle.Size = New-Object System.Drawing.Size(560, 24)
$lblTitle.Text = "ESTEIRA DE PÓS-PRODUÇÃO INTELIGENTE"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::White
$pnlHeader.Controls.Add($lblTitle)

$lblSubtitle = New-Object System.Windows.Forms.Label
$lblSubtitle.Location = New-Object System.Drawing.Point(22, 38)
$lblSubtitle.Size = New-Object System.Drawing.Size(560, 18)
$lblSubtitle.Text = "Projeto: $nomeAula  |  Origem: $dirEntrada"
$lblSubtitle.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblSubtitle.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$pnlHeader.Controls.Add($lblSubtitle)

# --- DIRETÓRIO DE DESTINO ---
$lblDestino = New-Object System.Windows.Forms.Label
$lblDestino.Location = New-Object System.Drawing.Point(20, 78)
$lblDestino.Size = New-Object System.Drawing.Size(120, 18)
$lblDestino.Text = "Pasta de Destino:"
$lblDestino.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($lblDestino)

$txtDestino = New-Object System.Windows.Forms.TextBox
$txtDestino.Location = New-Object System.Drawing.Point(20, 98)
$txtDestino.Size = New-Object System.Drawing.Size(465, 23)
$txtDestino.Text = $destinoSugerido
$txtDestino.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Controls.Add($txtDestino)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Location = New-Object System.Drawing.Point(495, 96)
$btnBrowse.Size = New-Object System.Drawing.Size(90, 27)
$btnBrowse.Text = "Procurar..."
$btnBrowse.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$btnBrowse.Add_Click({
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.SelectedPath = $txtDestino.Text
    $dlg.Description = "Selecione o diretorio final do projeto:"
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $txtDestino.Text = $dlg.SelectedPath
    }
})
$form.Controls.Add($btnBrowse)

# --- SELETOR DE PRESETS RÁPIDOS ---
$grpPreset = New-Object System.Windows.Forms.GroupBox
$grpPreset.Location = New-Object System.Drawing.Point(20, 135)
$grpPreset.Size = New-Object System.Drawing.Size(565, 68)
$grpPreset.Text = " 1. Modo de Operação (Preset Guiado) "
$grpPreset.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($grpPreset)

$cmbPresets = New-Object System.Windows.Forms.ComboBox
$cmbPresets.Location = New-Object System.Drawing.Point(18, 26)
$cmbPresets.Size = New-Object System.Drawing.Size(320, 24)
$cmbPresets.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$cmbPresets.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$cmbPresets.Items.AddRange(@(
    "🎓 Curso Completo (Tudo Ativado)",
    "📱 Foco em Redes (Cortes 9:16 + Hardsub)",
    "🎬 Pré-Edição NLE (Apenas Auto-Cut + Timeline EDL)",
    "🛠 Personalizado (Definir Manualmente)"
))
$cmbPresets.SelectedIndex = 0
$grpPreset.Controls.Add($cmbPresets)

$lblPresetDesc = New-Object System.Windows.Forms.Label
$lblPresetDesc.Location = New-Object System.Drawing.Point(350, 25)
$lblPresetDesc.Size = New-Object System.Drawing.Size(200, 32)
$lblPresetDesc.Text = "Pacote didático + cortes virais prontos."
$lblPresetDesc.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Italic)
$lblPresetDesc.ForeColor = [System.Drawing.Color]::FromArgb(100, 116, 139)
$grpPreset.Controls.Add($lblPresetDesc)

# --- ABAS DE CONFIGURAÇÃO DETALHADA ---
$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Location = New-Object System.Drawing.Point(20, 215)
$tabControl.Size = New-Object System.Drawing.Size(565, 290)
$tabControl.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($tabControl)

# ABA 1: Vídeo & Edição
$tabVideo = New-Object System.Windows.Forms.TabPage
$tabVideo.Text = "Corte & Áudio"
$tabVideo.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabVideo)

$chkAutoCut = New-Object System.Windows.Forms.CheckBox
$chkAutoCut.Location = New-Object System.Drawing.Point(20, 18)
$chkAutoCut.Size = New-Object System.Drawing.Size(510, 25)
$chkAutoCut.Text = "Ativar Auto-Cut Dinâmico (Fatiar pausas e respiração)"
$chkAutoCut.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkAutoCut.Checked = $true
$tabVideo.Controls.Add($chkAutoCut)

$lblSensibilidade = New-Object System.Windows.Forms.Label
$lblSensibilidade.Location = New-Object System.Drawing.Point(40, 48)
$lblSensibilidade.Size = New-Object System.Drawing.Size(180, 20)
$lblSensibilidade.Text = "Ritmo do Fatiamento:"
$tabVideo.Controls.Add($lblSensibilidade)

$cmbSensibilidade = New-Object System.Windows.Forms.ComboBox
$cmbSensibilidade.Location = New-Object System.Drawing.Point(40, 70)
$cmbSensibilidade.Size = New-Object System.Drawing.Size(220, 23)
$cmbSensibilidade.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$cmbSensibilidade.Items.AddRange(@(
    "Padrão (Pausas > 1.1s — Natural)",
    "Agressivo (Pausas > 0.8s — Super Rápido)",
    "Conservador (Pausas > 1.6s — Palestra)"
))
$cmbSensibilidade.SelectedIndex = 0
$tabVideo.Controls.Add($cmbSensibilidade)

$chkEDL = New-Object System.Windows.Forms.CheckBox
$chkEDL.Location = New-Object System.Drawing.Point(40, 110)
$chkEDL.Size = New-Object System.Drawing.Size(480, 24)
$chkEDL.Text = "Exportar Timeline EDL (DaVinci Resolve / Premiere)"
$chkEDL.Checked = $true
$tabVideo.Controls.Add($chkEDL)

$chkAudioBroadcast = New-Object System.Windows.Forms.CheckBox
$chkAudioBroadcast.Location = New-Object System.Drawing.Point(40, 140)
$chkAudioBroadcast.Size = New-Object System.Drawing.Size(480, 24)
$chkAudioBroadcast.Text = "Masterização de Áudio Broadcast (EBU R128 + Limpeza 80Hz)"
$chkAudioBroadcast.Checked = $true
$tabVideo.Controls.Add($chkAudioBroadcast)

$chkHardsubHoriz = New-Object System.Windows.Forms.CheckBox
$chkHardsubHoriz.Location = New-Object System.Drawing.Point(40, 170)
$chkHardsubHoriz.Size = New-Object System.Drawing.Size(480, 24)
$chkHardsubHoriz.Text = "Gerar Versão Horizontal Legendada (_DINAMICO_LEGENDADO.mp4)"
$chkHardsubHoriz.Checked = $true
$tabVideo.Controls.Add($chkHardsubHoriz)

# ABA 2: Material Didático
$tabDidatico = New-Object System.Windows.Forms.TabPage
$tabDidatico.Text = "Material & IA"
$tabDidatico.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabDidatico)

$chkSlides = New-Object System.Windows.Forms.CheckBox
$chkSlides.Location = New-Object System.Drawing.Point(20, 20)
$chkSlides.Size = New-Object System.Drawing.Size(510, 25)
$chkSlides.Text = "Detecção Inteligente de Slides (Scene Change)"
$chkSlides.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkSlides.Checked = $true
$tabDidatico.Controls.Add($chkSlides)

$chkPDF = New-Object System.Windows.Forms.CheckBox
$chkPDF.Location = New-Object System.Drawing.Point(40, 50)
$chkPDF.Size = New-Object System.Drawing.Size(480, 24)
$chkPDF.Text = "Compilar Apostila Ilustrada em PDF (via Edge Headless)"
$chkPDF.Checked = $true
$tabDidatico.Controls.Add($chkPDF)

$chkIA = New-Object System.Windows.Forms.CheckBox
$chkIA.Location = New-Object System.Drawing.Point(20, 95)
$chkIA.Size = New-Object System.Drawing.Size(510, 25)
$chkIA.Text = "Processamento Cognitivo Local (Llama 3.2 via Ollama)"
$chkIA.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkIA.Checked = $true
$tabDidatico.Controls.Add($chkIA)

$chkResumo = New-Object System.Windows.Forms.CheckBox
$chkResumo.Location = New-Object System.Drawing.Point(40, 125)
$chkResumo.Size = New-Object System.Drawing.Size(480, 24)
$chkResumo.Text = "Gerar Resumo Executivo Estruturado (Markdown)"
$chkResumo.Checked = $true
$tabDidatico.Controls.Add($chkResumo)

$chkQuiz = New-Object System.Windows.Forms.CheckBox
$chkQuiz.Location = New-Object System.Drawing.Point(40, 155)
$chkQuiz.Size = New-Object System.Drawing.Size(480, 24)
$chkQuiz.Text = "Gerar Quiz Interativo de Fixação com Gabarito (HTML)"
$chkQuiz.Checked = $true
$tabDidatico.Controls.Add($chkQuiz)

# ABA 3: Redes Sociais
$tabRedes = New-Object System.Windows.Forms.TabPage
$tabRedes.Text = "Redes Sociais (9:16)"
$tabRedes.BackColor = [System.Drawing.Color]::White
$tabControl.TabPages.Add($tabRedes)

$chkCortes = New-Object System.Windows.Forms.CheckBox
$chkCortes.Location = New-Object System.Drawing.Point(20, 20)
$chkCortes.Size = New-Object System.Drawing.Size(510, 25)
$chkCortes.Text = "Ativar Curadoria Viral e Cortes 9:16 para TikTok / Shorts / Reels"
$chkCortes.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkCortes.Checked = $true
$tabRedes.Controls.Add($chkCortes)

$lblNumCortes = New-Object System.Windows.Forms.Label
$lblNumCortes.Location = New-Object System.Drawing.Point(40, 55)
$lblNumCortes.Size = New-Object System.Drawing.Size(200, 20)
$lblNumCortes.Text = "Quantidade de Clipes Selecionados:"
$tabRedes.Controls.Add($lblNumCortes)

$numCortes = New-Object System.Windows.Forms.NumericUpDown
$numCortes.Location = New-Object System.Drawing.Point(40, 78)
$numCortes.Size = New-Object System.Drawing.Size(70, 23)
$numCortes.Minimum = 1
$numCortes.Maximum = 6
$numCortes.Value = 3
$tabRedes.Controls.Add($numCortes)

$lblLayout = New-Object System.Windows.Forms.Label
$lblLayout.Location = New-Object System.Drawing.Point(40, 120)
$lblLayout.Size = New-Object System.Drawing.Size(480, 45)
$lblLayout.Text = "Layout: Vídeo 1080x1920 vertical com fundo em desfoque dinâmico (Gaussian Blur), vídeo central nítido e legenda de alto contraste sincronizada."
$lblLayout.ForeColor = [System.Drawing.Color]::FromArgb(71, 85, 105)
$tabRedes.Controls.Add($lblLayout)

# --- LÓGICA DE PRESETS AUTOMÁTICOS ---
$cmbPresets.Add_SelectedIndexChanged({
    switch ($cmbPresets.SelectedIndex) {
        0 { # Curso Completo
            $lblPresetDesc.Text = "Pacote didático + cortes virais prontos."
            $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true
            $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $true; $chkPDF.Checked = $true
            $chkIA.Checked = $true; $chkResumo.Checked = $true; $chkQuiz.Checked = $true
            $chkCortes.Checked = $true
        }
        1 { # Redes
            $lblPresetDesc.Text = "Foco em engajamento rápido e mobile."
            $chkAutoCut.Checked = $true; $chkEDL.Checked = $false; $chkAudioBroadcast.Checked = $true
            $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $false; $chkPDF.Checked = $false
            $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false
            $chkCortes.Checked = $true
        }
        2 { # Pré-Edição NLE
            $lblPresetDesc.Text = "Prepara arquivos e timeline para editor."
            $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true
            $chkHardsubHoriz.Checked = $false; $chkSlides.Checked = $false; $chkPDF.Checked = $false
            $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false
            $chkCortes.Checked = $false
        }
        3 { # Personalizado
            $lblPresetDesc.Text = "Ajuste os parâmetros livremente nas abas."
        }
    }
})

# --- RODAPÉ COM BOTÕES ---
$btnIniciar = New-Object System.Windows.Forms.Button
$btnIniciar.Location = New-Object System.Drawing.Point(345, 525)
$btnIniciar.Size = New-Object System.Drawing.Size(240, 48)
$btnIniciar.Text = "▶ INICIAR PROCESSAMENTO"
$btnIniciar.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnIniciar.ForeColor = [System.Drawing.Color]::White
$btnIniciar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnIniciar.FlatAppearance.BorderSize = 0
$btnIniciar.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($btnIniciar)

$btnCancelar = New-Object System.Windows.Forms.Button
$btnCancelar.Location = New-Object System.Drawing.Point(220, 525)
$btnCancelar.Size = New-Object System.Drawing.Size(115, 48)
$btnCancelar.Text = "Cancelar"
$btnCancelar.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$btnCancelar.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($btnCancelar)

$form.AcceptButton = $btnIniciar
$form.CancelButton = $btnCancelar

$res = $form.ShowDialog()
if ($res -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "[CANCELADO] Operacao interrompida pelo usuario." -ForegroundColor Yellow
    exit 0
}

# Coleta de Parâmetros Finais
$dirSaida       = $txtDestino.Text.Trim()
$fazerAutoCut   = $chkAutoCut.Checked
$fazerEDL       = $chkEDL.Checked
$fazerHardsub   = $chkHardsubHoriz.Checked
$fazerSlides    = $chkSlides.Checked
$fazerPDF       = $chkPDF.Checked
$fazerIA        = $chkIA.Checked
$fazerCortes    = $chkCortes.Checked
$qtdCortes      = [int]$numCortes.Value

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
    if ($videos.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show("Nenhum arquivo de video compativel foi localizado.", "Aviso", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        exit 0
    }
}

Write-Host "`n=========================================================" -ForegroundColor Cyan
Write-Host "   LUIS-MEDIA-TOOLS: EXECUÇÃO MASTER                    " -ForegroundColor Cyan
Write-Host "   Projeto:    $nomeAula                                 " -ForegroundColor Cyan
Write-Host "   Destino:    $dirSaida                                 " -ForegroundColor Cyan
Write-Host "   Auto-Cut:   $fazerAutoCut | Hardsub: $fazerHardsub    " -ForegroundColor Cyan
Write-Host "   Slides:     $fazerSlides  | IA Local: $fazerIA        " -ForegroundColor Cyan
Write-Host "   Cortes:     $fazerCortes ($qtdCortes clipes)          " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()

foreach ($video in $videos) {
    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    Write-Host "`n>>> [PROCESSANDO] $nome ..." -ForegroundColor Green

    # 1. Auto-Cut Dinâmico com Transição Suave
    $videoAlvo = $video.FullName
    if ($fazerAutoCut) {
        $videoDinamico = Join-Path $dirSaida "${nome}_DINAMICO.mp4"
        if (-not (Test-Path $videoDinamico)) {
            Write-Host "    Fatiando silencios (Anti-Estalo)..." -ForegroundColor DarkYellow
            & python (Join-Path $raiz "autocut_engine.py") $video.FullName $dirSaida
            if ($fazerEDL) {
                Get-ChildItem -Path $dirSaida -Filter "${nome}_timeline_cortes.edl" | Move-Item -Destination $pastas["7"] -Force -ErrorAction SilentlyContinue
            }
        }
        if (Test-Path $videoDinamico) { $videoAlvo = $videoDinamico }
    }

    # 2. Minutagem Acumulada
    $duracaoStr = (& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $videoAlvo)
    $duracao = 0.0
    [double]::TryParse($duracaoStr, [System.Globalization.NumberStyles]::Any, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$duracao) | Out-Null
    $horas = [math]::Floor($tempoAcumulado / 3600)
    $minutos = [math]::Floor(($tempoAcumulado % 3600) / 60)
    $segundos = [math]::Floor($tempoAcumulado % 60)
    $stamp = if ($horas -gt 0) { "{0:D2}:{1:D2}:{2:D2}" -f [int]$horas, [int]$minutos, [int]$segundos } else { "{0:D2}:{1:D2}" -f [int]$minutos, [int]$segundos }
    $listaCapitulos += "$stamp - $nome"
    $tempoAcumulado += $duracao

    # 3. Extrair Áudio Bruto
    $audioBrutoTemp = Join-Path $dirTempChunk "$nome.wav"
    if (-not (Test-Path $audioBrutoTemp)) {
        & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vn -acodec pcm_s16le -ar 16000 -ac 1 $audioBrutoTemp
    }

    # 4. Tratamento Broadcast
    $audioTratTemp = Join-Path $dirTempChunk "$($nome)_tratado.wav"
    if (-not (Test-Path $audioTratTemp)) {
        Write-Host "    Tratando audio (EBU R128 + Limpeza)..." -ForegroundColor DarkCyan
        & ffmpeg -hide_banner -loglevel error -y -i $audioBrutoTemp -af "highpass=f=80,loudnorm=I=-16:LRA=11:TP=-1.5" $audioTratTemp
    }

    # 5. Whisper Transcrição
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

    # 6. Hardsub Horizontal
    if ($fazerHardsub -and (Test-Path $srtTemp)) {
        $videoLegendado = Join-Path $dirSaida "${nome}_DINAMICO_LEGENDADO.mp4"
        if (-not (Test-Path $videoLegendado)) {
            Write-Host "    Renderizando versao dinamica com Hardsub..." -ForegroundColor Magenta
            $srtFormatado = $srtTemp.Replace("\", "/").Replace(":", "\:")
            $estiloLegenda = "FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,MarginV=25"
            & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo `
                -vf "subtitles='$srtFormatado':force_style='$estiloLegenda'" `
                -c:v libx264 -preset faster -crf 20 -c:a copy $videoLegendado
        }
    }

    if (Test-Path $srtTemp) { Copy-Item -Path (Join-Path $dirTempChunk "$nome.*") -Destination $pastas["1"] -Force }
    if (Test-Path $audioBrutoTemp) { Copy-Item -Path $audioBrutoTemp -Destination $pastas["2"] -Force }
    if (Test-Path $audioTratTemp) { Copy-Item -Path $audioTratTemp -Destination $pastas["3"] -Force }
}

$listaCapitulos | Out-File -FilePath $minutagemArquivo -Encoding UTF8

# 7. Slides e Apostila PDF
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

    if ($fazerPDF -and (Test-Path (Join-Path $raiz "editorial_engine.py"))) {
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

# 8. IA Local Llama
if ($fazerIA -and (Test-Path (Join-Path $raiz "gerador_ia.py"))) {
    Write-Host "`n>>> [IA LOCAL - LLAMA] Criando Resumo e Quiz..." -ForegroundColor Magenta
    & python (Join-Path $raiz "gerador_ia.py") $dirSaida
}

# 9. Cortes 9:16 para Redes
if ($fazerCortes -and (Test-Path (Join-Path $raiz "gerador_cortes.py"))) {
    Write-Host "`n>>> [CORTES VIRAIS 9:16] Renderizando clipes para redes..." -ForegroundColor DarkCyan
    & python (Join-Path $raiz "gerador_cortes.py") $dirSaida
}

# 10. Limpeza intermediária
Get-ChildItem -Path $dirSaida -Directory | Where-Object { $_.Name -match "^$($nomeAula)-\d+" -or $_.Name -match "^Aula\d+-\d+" } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# 11. Empacotamento ZIP
Write-Host "`n>>> [EMPACOTAMENTO] Gerando entregavel ZIP..." -ForegroundColor Cyan
$arquivoZip = Join-Path $dirSaida "Entregavel-$nomeAula.zip"
Compress-Archive -Path $pastas["1"], $pastas["2"], $pastas["3"], $pastas["4"], $pastas["5"], $pastas["6"], $pastas["7"] -DestinationPath $arquivoZip -Force

# 12. Faxina de intermediários (SSD protegido)
if ((Test-Path $arquivoZip) -and ((Get-Item $arquivoZip).Length -gt 1024)) {
    foreach ($p in $pastas.Values) {
        if (Test-Path $p) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
    }
}

# 13. Mover vídeos brutos para a raiz do destino
foreach ($video in $videos) {
    if ($video.DirectoryName -ne $dirSaida) {
        $destinoFinalVideo = Join-Path $dirSaida $video.Name
        Move-Item -LiteralPath $video.FullName -Destination $destinoFinalVideo -Force
    }
}

# 14. Limpeza da pasta de origem
if ((Test-Path $dirEntrada) -and ($dirEntrada -ne $dirSaida) -and ($dirEntrada -ne $raiz)) {
    $itensRestantes = Get-ChildItem -Path $dirEntrada -Force
    if ($itensRestantes.Count -eq 0) {
        Remove-Item -LiteralPath $dirEntrada -Force -ErrorAction SilentlyContinue
    }
}

# 15. Notificação e Abertura
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
Write-Host "   ESTEIRA CONCLUIDA COM SUCESSO!                       " -ForegroundColor Green
Write-Host "   Destino:    $dirSaida                                " -ForegroundColor Green
Write-Host "   Entregavel: $arquivoZip                              " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
