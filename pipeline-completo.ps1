param(
    [string]$Aula = "",
    [string]$CaminhoPasta = "",
    [string]$PastaDestino = ""
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- SUPORTE A DWM DARK & BLUR ACRÍLICO ---
if (-not ([System.Management.Automation.PSTypeName]'Win32Dwm').Type) {
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public class Win32Dwm {
        [DllImport("dwmapi.dll", SetLastError = false)]
        public static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int attrValue, int attrSize);
    }
"@
}

function Global:Aplicar-TemaModerno {
    $darkBg = [System.Drawing.Color]::FromArgb(18, 19, 28);
    $cardBg = [System.Drawing.Color]::FromArgb(28, 30, 42);
    $textLight = [System.Drawing.Color]::FromArgb(240, 243, 248);
    $accent = [System.Drawing.Color]::FromArgb(129, 140, 248);

    $form.BackColor = $darkBg;
    $form.ForeColor = $textLight;

    try {
        if ($form.IsHandleCreated) {
            [int]$dark = 1;
            [int]$acrylic = 3;
            [void][Win32Dwm]::DwmSetWindowAttribute($form.Handle, 20, [ref]$dark, 4);
            [void][Win32Dwm]::DwmSetWindowAttribute($form.Handle, 38, [ref]$acrylic, 4);
        }
    } catch { };

    if ($trackOpacidade) {
        $form.Opacity = ($trackOpacidade.Value / 100.0);
    };

    $estilizar = {
        param($ctrl);
        if ($ctrl -is [System.Windows.Forms.TabPage]) {
            $ctrl.UseVisualStyleBackColor = $false;
            $ctrl.BackColor = $darkBg;
            $ctrl.ForeColor = $textLight;
        }
        elseif ($ctrl -is [System.Windows.Forms.GroupBox]) {
            $ctrl.BackColor = $darkBg;
            $ctrl.ForeColor = $accent;
        }
        elseif ($ctrl -is [System.Windows.Forms.Label]) {
            if ($ctrl -eq $lblPausa -or $ctrl -eq $lblOpacidade) {
                $ctrl.ForeColor = [System.Drawing.Color]::FromArgb(220, 225, 240);
            } elseif ($ctrl -ne $lblPausaVal -and $ctrl -ne $lblOpacidadeVal) {
                $ctrl.ForeColor = $textLight;
            }
        }
        elseif ($ctrl -is [System.Windows.Forms.TextBox] -or $ctrl -is [System.Windows.Forms.CheckedListBox] -or $ctrl -is [System.Windows.Forms.ListBox] -or $ctrl -is [System.Windows.Forms.ComboBox]) {
            $ctrl.BackColor = $cardBg;
            $ctrl.ForeColor = $textLight;
        }
        elseif ($ctrl -is [System.Windows.Forms.Button] -and $ctrl -ne $btnIniciar -and $ctrl -ne $btnBlur) {
            $ctrl.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat;
            $ctrl.FlatAppearance.BorderSize = 1;
            $ctrl.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(75, 85, 110);
            $ctrl.BackColor = $cardBg;
            $ctrl.ForeColor = $textLight;
        }
        if ($ctrl.Controls) {
            foreach ($filho in ($ctrl.Controls)) {
                & $estilizar $filho;
            }
        }
    };
    & $estilizar $form;

    if ($btnBlur) {
        $btnBlur.Text = "✨ Tema: DARK + BLUR";
        $btnBlur.BackColor = [System.Drawing.Color]::FromArgb(38, 40, 58);
        $btnBlur.ForeColor = [System.Drawing.Color]::FromArgb(165, 180, 252);
    };
}

function Global:Aplicar-TemaClassico {
    $form.BackColor = [System.Drawing.SystemColors]::Control;
    $form.ForeColor = [System.Drawing.SystemColors]::ControlText;

    try {
        if ($form.IsHandleCreated) {
            [int]$dark = 0;
            [int]$modo = 1;
            [void][Win32Dwm]::DwmSetWindowAttribute($form.Handle, 20, [ref]$dark, 4);
            [void][Win32Dwm]::DwmSetWindowAttribute($form.Handle, 38, [ref]$modo, 4);
        }
    } catch { };

    $form.Opacity = 1.0;

    $restaurar = {
        param($ctrl);
        if ($ctrl -is [System.Windows.Forms.TabPage]) {
            $ctrl.BackColor = [System.Drawing.SystemColors]::Window;
            $ctrl.ForeColor = [System.Drawing.SystemColors]::ControlText;
        }
        elseif ($ctrl -is [System.Windows.Forms.GroupBox]) {
            $ctrl.BackColor = [System.Drawing.SystemColors]::Control;
            $ctrl.ForeColor = [System.Drawing.SystemColors]::ControlText;
        }
        elseif ($ctrl -is [System.Windows.Forms.Label]) {
            if ($ctrl -eq $lblPausa -or $ctrl -eq $lblOpacidade) {
                $ctrl.ForeColor = [System.Drawing.Color]::FromArgb(31, 41, 55);
            } elseif ($ctrl -ne $lblPausaVal -and $ctrl -ne $lblOpacidadeVal) {
                $ctrl.ForeColor = [System.Drawing.SystemColors]::ControlText;
            }
        }
        elseif ($ctrl -is [System.Windows.Forms.TextBox] -or $ctrl -is [System.Windows.Forms.CheckedListBox] -or $ctrl -is [System.Windows.Forms.ListBox] -or $ctrl -is [System.Windows.Forms.ComboBox]) {
            $ctrl.BackColor = [System.Drawing.SystemColors]::Window;
            $ctrl.ForeColor = [System.Drawing.SystemColors]::WindowText;
        }
        elseif ($ctrl -is [System.Windows.Forms.Button] -and $ctrl -ne $btnIniciar -and $ctrl -ne $btnBlur) {
            $ctrl.FlatStyle = [System.Windows.Forms.FlatStyle]::Standard;
            $ctrl.BackColor = [System.Drawing.SystemColors]::ControlLight;
            $ctrl.ForeColor = [System.Drawing.SystemColors]::ControlText;
        }
        if ($ctrl.Controls) {
            foreach ($filho in ($ctrl.Controls)) {
                & $restaurar $filho;
            }
        }
    };
    & $restaurar $form;

    if ($btnBlur) {
        $btnBlur.Text = "⚪ Tema: CLÁSSICO";
        $btnBlur.BackColor = [System.Drawing.Color]::FromArgb(235, 235, 240);
        $btnBlur.ForeColor = [System.Drawing.Color]::FromArgb(50, 50, 60);
    };
}


function Global:Obter-DuracaoVideo([string]$caminhoArquivo) {
    if (-not (Test-Path -LiteralPath $caminhoArquivo)) { return "" }
    try {
        $raw = & ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$caminhoArquivo" 2>$null
        if ($raw) {
            $secVal = 0.0
            $cultura = [System.Globalization.CultureInfo]::InvariantCulture
            if ([double]::TryParse($raw.Trim(), [System.Globalization.NumberStyles]::Any, $cultura, [ref]$secVal)) {
                $ts = [TimeSpan]::FromSeconds($secVal)
                if ($ts.Hours -gt 0) {
                    return ("{0}h {1:D2}m {2:D2}s" -f $ts.Hours, $ts.Minutes, $ts.Seconds)
                } else {
                    return ("{0}m {1:D2}s" -f $ts.Minutes, $ts.Seconds)
                }
            }
        }
    } catch { }
    return ""
}

# Pasta do proprio programa (funciona como .ps1 e quando compilado em .exe)
$raiz = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($raiz)) { $raiz = [System.AppDomain]::CurrentDomain.BaseDirectory.TrimEnd('\') }
$configFile = Join-Path $raiz "config_presets.json"

$cfg = @{
    PresetIndex = 0; AutoCut = $true; EDL = $true; Hardsub =$true
    Slides = $true; PDF =$true; IA = $true; Resumo =$true; Quiz = $true; Cortes =$true; QtdCortes = 3
    Audio = $true; Encoder = 0; Pausa = 25
}

if (Test-Path $configFile) {
    try {
        $jsonContent = Get-Content $configFile -Raw | ConvertFrom-Json
        if ($jsonContent) {
            foreach ($key in $jsonContent.psobject.properties.name) {
                $cfg[$key] = $jsonContent.$key
            }
        }
    } catch { }
}

if ($CaminhoPasta -ne "") {
    $itemAlvo = Get-Item -LiteralPath $CaminhoPasta
    if ($itemAlvo.PSIsContainer) { $dirEntrada =$itemAlvo.FullName; $nomeAula =$itemAlvo.Name }
    else { $dirEntrada = $itemAlvo.DirectoryName; $nomeAula = (Get-Item $dirEntrada).Name }
} else {
    if ($Aula -eq "") { $Aula = "Aula1" }
    $nomeAula =$Aula; $dirEntrada = Join-Path $raiz "entrada\$nomeAula"
}

if (-not (Test-Path $dirEntrada)) {
    [void][System.Windows.Forms.MessageBox]::Show("Pasta de entrada nao encontrada:`n$dirEntrada", "Erro", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    exit 1
}

# --- FORMULÁRIO PRINCIPAL ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "LUIS-MEDIA-TOOLS — Production Studio Hub"
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None
$form.ClientSize = New-Object System.Drawing.Size(620, 620)
$form.MinimumSize = New-Object System.Drawing.Size(620, 620)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(18, 19, 28)

# Cabeçalho Superior
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

# Barra de Destino (Inicia Vazia)
$lblDestino = New-Object System.Windows.Forms.Label
$lblDestino.Text = "Pasta de Destino:"
$lblDestino.Location = New-Object System.Drawing.Point(18, 75)
$lblDestino.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblDestino.ForeColor = [System.Drawing.Color]::FromArgb(199, 210, 254)
$lblDestino.AutoSize = $true
$form.Controls.Add($lblDestino)

$txtDestino = New-Object System.Windows.Forms.TextBox
$txtDestino.Location = New-Object System.Drawing.Point(18, 97)
$txtDestino.Size = New-Object System.Drawing.Size(465, 27)
$txtDestino.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$txtDestino.BackColor = [System.Drawing.Color]::FromArgb(26, 28, 40)
$txtDestino.ForeColor = [System.Drawing.Color]::FromArgb(241, 245, 249)
$txtDestino.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$txtDestino.Text = ""
$form.Controls.Add($txtDestino)

$btnBrowse = New-Object System.Windows.Forms.Button
$btnBrowse.Text = "Procurar..."
$btnBrowse.Location = New-Object System.Drawing.Point(490, 96)
$btnBrowse.Size = New-Object System.Drawing.Size(105, 28)
$btnBrowse.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$btnBrowse.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnBrowse.FlatAppearance.BorderSize = 1
$btnBrowse.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(99, 102, 241)
$btnBrowse.BackColor = [System.Drawing.Color]::FromArgb(38, 41, 58)
$btnBrowse.ForeColor = [System.Drawing.Color]::FromArgb(199, 210, 254)
$btnBrowse.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnBrowse.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    if (-not [string]::IsNullOrWhiteSpace($txtDestino.Text) -and (Test-Path -LiteralPath $txtDestino.Text)) {
        $dialog.SelectedPath = $txtDestino.Text
    }
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        $txtDestino.Text = $dialog.SelectedPath
    }
})
$form.Controls.Add($btnBrowse)

# Grupo de Presets
$grpPreset = New-Object System.Windows.Forms.GroupBox
$grpPreset.Location = New-Object System.Drawing.Point(20, 135)
$grpPreset.Size = New-Object System.Drawing.Size(575, 68)
$grpPreset.Text = " 1. Modo de Operação (Preset Guiado) "
$grpPreset.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($grpPreset)

$cmbPresets = New-Object System.Windows.Forms.ComboBox
$cmbPresets.Location = New-Object System.Drawing.Point(18, 26)
$cmbPresets.Size = New-Object System.Drawing.Size(320, 24)
$cmbPresets.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$cmbPresets.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$cmbPresets.Items.AddRange(@("🎓 Curso Completo (Tudo Ativado)", "📱 Foco em Redes (Cortes 9:16 + Hardsub)", "🎬 Pré-Edição NLE (Apenas Auto-Cut + Timeline EDL)", "🛠 Personalizado"))
$cmbPresets.SelectedIndex = $cfg.PresetIndex
$grpPreset.Controls.Add($cmbPresets)

$lblPresetDesc = New-Object System.Windows.Forms.Label
$lblPresetDesc.Location = New-Object System.Drawing.Point(350, 25); $lblPresetDesc.Size = New-Object System.Drawing.Size(210, 32)
$lblPresetDesc.Text = "Voz Broadcast + Legenda Fluida para Aulas."
$lblPresetDesc.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Italic)
$lblPresetDesc.ForeColor = [System.Drawing.Color]::FromArgb(148, 163, 184)
$grpPreset.Controls.Add($lblPresetDesc)

# Abas de Configuração
$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Location = New-Object System.Drawing.Point(20, 215)
$tabControl.Size = New-Object System.Drawing.Size(575, 235)
$tabControl.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($tabControl)

$tabSelecao = New-Object System.Windows.Forms.TabPage; $tabSelecao.Text = "📁 Selecionar Vídeos"
$tabControl.TabPages.Add($tabSelecao)

$lblInfoSel = New-Object System.Windows.Forms.Label
$lblInfoSel.Text = "Selecione os vídeos que deseja tratar nesta execução:"
$lblInfoSel.Location = New-Object System.Drawing.Point(15, 12); $lblInfoSel.Size = New-Object System.Drawing.Size(400, 20)
$lblInfoSel.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$tabSelecao.Controls.Add($lblInfoSel)

$chkListVideos = New-Object System.Windows.Forms.CheckedListBox
$chkListVideos.Location = New-Object System.Drawing.Point(15, 36)
$chkListVideos.Size = New-Object System.Drawing.Size(540, 130)
$chkListVideos.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$chkListVideos.CheckOnClick = $true

$global:mapaVideos = @{}
if (Test-Path $dirEntrada) {
    $arquivosDisco = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
    foreach ($arq in $arquivosDisco) {
        $dur = Obter-DuracaoVideo $arq.FullName
        $rotulo = if ($dur) { "$($arq.Name)  [$dur]" } else { $arq.Name }
        $global:mapaVideos[$rotulo] = $arq.FullName
        [void]$chkListVideos.Items.Add($rotulo, $true)
    }
}
$tabSelecao.Controls.Add($chkListVideos)

$btnTodos = New-Object System.Windows.Forms.Button
$btnTodos.Text = "Marcar Todos"; $btnTodos.Location = New-Object System.Drawing.Point(15, 172); $btnTodos.Size = New-Object System.Drawing.Size(120, 26)
$btnTodos.Add_Click({ for ($i = 0; $i -lt $chkListVideos.Items.Count; $i++) { $chkListVideos.SetItemChecked($i, $true) } })
$tabSelecao.Controls.Add($btnTodos)

$btnNenhum = New-Object System.Windows.Forms.Button
$btnNenhum.Text = "Desmarcar Todos"; $btnNenhum.Location = New-Object System.Drawing.Point(145, 172); $btnNenhum.Size = New-Object System.Drawing.Size(130, 26)
$btnNenhum.Add_Click({ for ($i = 0; $i -lt $chkListVideos.Items.Count; $i++) { $chkListVideos.SetItemChecked($i, $false) } })
$tabSelecao.Controls.Add($btnNenhum)

$tabVideo = New-Object System.Windows.Forms.TabPage; $tabVideo.Text = "Corte & Voz Pro"
$tabControl.TabPages.Add($tabVideo)

$chkAutoCut = New-Object System.Windows.Forms.CheckBox; $chkAutoCut.Location = New-Object System.Drawing.Point(20, 18); $chkAutoCut.Size = New-Object System.Drawing.Size(510, 25)
$chkAutoCut.Text = "Ativar Auto-Cut Dinâmico (Fatiar pausas)"; $chkAutoCut.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkAutoCut.Checked = $cfg.AutoCut; $tabVideo.Controls.Add($chkAutoCut)

$chkEDL = New-Object System.Windows.Forms.CheckBox; $chkEDL.Location = New-Object System.Drawing.Point(40, 52); $chkEDL.Size = New-Object System.Drawing.Size(480, 24)
$chkEDL.Text = "Exportar Timeline EDL (DaVinci Resolve / Premiere)"; $chkEDL.Checked = $cfg.EDL; $tabVideo.Controls.Add($chkEDL)

$chkAudioBroadcast = New-Object System.Windows.Forms.CheckBox; $chkAudioBroadcast.Location = New-Object System.Drawing.Point(40, 82); $chkAudioBroadcast.Size = New-Object System.Drawing.Size(480, 24)
$chkAudioBroadcast.Text = "Masterização de Voz de Estúdio (Equalização + R128 -14 LUFS)"; $chkAudioBroadcast.Checked = [bool]$cfg.Audio; $tabVideo.Controls.Add($chkAudioBroadcast)

$chkHardsubHoriz = New-Object System.Windows.Forms.CheckBox; $chkHardsubHoriz.Location = New-Object System.Drawing.Point(40, 112); $chkHardsubHoriz.Size = New-Object System.Drawing.Size(480, 24)
$chkHardsubHoriz.Text = "Gerar Versão Horizontal com Legenda Fluida na Borda"; $chkHardsubHoriz.Checked = $cfg.Hardsub; $tabVideo.Controls.Add($chkHardsubHoriz)

$lblEncoder = New-Object System.Windows.Forms.Label
$lblEncoder.Text = "Aceleração / Hardware:"
$lblEncoder.Location = New-Object System.Drawing.Point(40, 146)
$lblEncoder.Size = New-Object System.Drawing.Size(140, 20)
$lblEncoder.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$tabVideo.Controls.Add($lblEncoder)

$cmbEncoder = New-Object System.Windows.Forms.ComboBox
$cmbEncoder.Location = New-Object System.Drawing.Point(185, 143)
$cmbEncoder.Size = New-Object System.Drawing.Size(335, 24)
$cmbEncoder.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$cmbEncoder.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$cmbEncoder.Items.AddRange(@(
    "🔍 Automático (testa a placa e escolhe o melhor)",
    "⚡ GPU AMD (AMF - Radeon Vega / Ryzen 5600GT)",
    "🖥️ Processador CPU (x264 - Compatibilidade Total)",
    "🟢 GPU NVIDIA (NVENC - GeForce)",
    "🔷 GPU Intel (QSV - QuickSync)"
))
$cmbEncoder.SelectedIndex = [Math]::Min([Math]::Max(0, [int]$cfg.Encoder), 4)
$tabVideo.Controls.Add($cmbEncoder)

$tabDidatico = New-Object System.Windows.Forms.TabPage; $tabDidatico.Text = "Material & IA"
$tabControl.TabPages.Add($tabDidatico)

$chkSlides = New-Object System.Windows.Forms.CheckBox; $chkSlides.Location = New-Object System.Drawing.Point(20, 18); $chkSlides.Size = New-Object System.Drawing.Size(510, 25)
$chkSlides.Text = "Detecção Inteligente de Slides"; $chkSlides.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkSlides.Checked = $cfg.Slides; $tabDidatico.Controls.Add($chkSlides)

$chkPDF = New-Object System.Windows.Forms.CheckBox; $chkPDF.Location = New-Object System.Drawing.Point(40, 48); $chkPDF.Size = New-Object System.Drawing.Size(480, 24)
$chkPDF.Text = "Compilar Apostila Ilustrada em PDF"; $chkPDF.Checked = $cfg.PDF; $tabDidatico.Controls.Add($chkPDF)

$chkIA = New-Object System.Windows.Forms.CheckBox; $chkIA.Location = New-Object System.Drawing.Point(20, 88); $chkIA.Size = New-Object System.Drawing.Size(510, 25)
$chkIA.Text = "Processamento Cognitivo Local (Llama 3.2)"; $chkIA.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkIA.Checked = $cfg.IA; $tabDidatico.Controls.Add($chkIA)

$chkResumo = New-Object System.Windows.Forms.CheckBox; $chkResumo.Location = New-Object System.Drawing.Point(40, 118); $chkResumo.Size = New-Object System.Drawing.Size(480, 24)
$chkResumo.Text = "Gerar Resumo Executivo Estruturado"; $chkResumo.Checked = $cfg.Resumo; $tabDidatico.Controls.Add($chkResumo)

$chkQuiz = New-Object System.Windows.Forms.CheckBox; $chkQuiz.Location = New-Object System.Drawing.Point(40, 148); $chkQuiz.Size = New-Object System.Drawing.Size(480, 24)
$chkQuiz.Text = "Gerar Quiz Interativo de Fixação"; $chkQuiz.Checked = $cfg.Quiz; $tabDidatico.Controls.Add($chkQuiz)

$tabRedes = New-Object System.Windows.Forms.TabPage; $tabRedes.Text = "Redes Sociais (9:16)"
$tabControl.TabPages.Add($tabRedes)

$chkCortes = New-Object System.Windows.Forms.CheckBox; $chkCortes.Location = New-Object System.Drawing.Point(20, 20); $chkCortes.Size = New-Object System.Drawing.Size(510, 25)
$chkCortes.Text = "Ativar Curadoria Viral e Cortes 9:16"; $chkCortes.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$chkCortes.Checked = $cfg.Cortes; $tabRedes.Controls.Add($chkCortes)

$lblQtdCortes = New-Object System.Windows.Forms.Label
$lblQtdCortes.Text = "Quantidade de cortes por vídeo:"; $lblQtdCortes.Location = New-Object System.Drawing.Point(40, 58); $lblQtdCortes.Size = New-Object System.Drawing.Size(200, 22)
$tabRedes.Controls.Add($lblQtdCortes)
$numCortes = New-Object System.Windows.Forms.NumericUpDown
$numCortes.Location = New-Object System.Drawing.Point(245, 55); $numCortes.Size = New-Object System.Drawing.Size(60, 24)
$numCortes.Minimum = 1; $numCortes.Maximum = 10; $numCortes.Value = [Math]::Min([Math]::Max(1, [int]$cfg.QtdCortes), 10)
$tabRedes.Controls.Add($numCortes)

$lblCortesInfo = New-Object System.Windows.Forms.Label
$lblCortesInfo.Text = "A IA local escolhe os trechos mais fortes (20-60 s) e gera vídeos 1080x1920 com legenda grande."
$lblCortesInfo.Location = New-Object System.Drawing.Point(40, 92); $lblCortesInfo.Size = New-Object System.Drawing.Size(500, 40)
$lblCortesInfo.Font = New-Object System.Drawing.Font("Segoe UI", 8, [System.Drawing.FontStyle]::Italic)
$tabRedes.Controls.Add($lblCortesInfo)

$cmbPresets.Add_SelectedIndexChanged({
    switch ($cmbPresets.SelectedIndex) {
        0 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $true; $chkPDF.Checked = $true; $chkIA.Checked = $true; $chkResumo.Checked = $true; $chkQuiz.Checked = $true; $chkCortes.Checked = $true }
        1 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $false; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $true; $chkSlides.Checked = $false; $chkPDF.Checked = $false; $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false; $chkCortes.Checked = $true }
        2 { $chkAutoCut.Checked = $true; $chkEDL.Checked = $true; $chkAudioBroadcast.Checked = $true; $chkHardsubHoriz.Checked = $false; $chkSlides.Checked = $false; $chkPDF.Checked = $false; $chkIA.Checked = $false; $chkResumo.Checked = $false; $chkQuiz.Checked = $false; $chkCortes.Checked = $false }
    }
})

# Drag and Drop Limpo (Só ativa quando você solta arquivos com o mouse)
$acaoDragEnter = {
    param($sender, $e)
    try {
        if ($e.Data -and $e.Data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) {
            $e.Effect = [System.Windows.Forms.DragDropEffects]::Copy
        }
    } catch { }
}

$acaoDragDrop = {
    param($sender, $e)
    try {
        if ($e.Data -and $e.Data.GetDataPresent([System.Windows.Forms.DataFormats]::FileDrop)) {
            $files = $e.Data.GetData([System.Windows.Forms.DataFormats]::FileDrop)
            if ($files) {
                $adicionados = 0
                foreach ($f in $files) {
                    $abs = [System.IO.Path]::GetFullPath($f)
                    $name = [System.IO.Path]::GetFileName($abs)
                    
                    # Evita duplicatas conferindo o caminho real
                    if ($global:mapaVideos.Values -contains $abs) { continue }
                    
                    $dur = Obter-DuracaoVideo $abs
                    $rotulo = if ($dur) { "$name  [$dur]" } else { $name }
                    
                    $global:mapaVideos[$rotulo] = $abs
                    [void]$chkListVideos.Items.Add($rotulo, $true)
                    $adicionados++
                }
                if ($adicionados -gt 0) {
                    Write-Host "[DRAG & DROP] $adicionados novo(s) video(s) com duracao adicionado(s)!" -ForegroundColor Green
                }
            }
        }
    } catch { }
}
$form.AllowDrop = $true; $form.Add_DragEnter($acaoDragEnter); $form.Add_DragDrop($acaoDragDrop)
$chkListVideos.AllowDrop = $true; $chkListVideos.Add_DragEnter($acaoDragEnter); $chkListVideos.Add_DragDrop($acaoDragDrop)
$tabSelecao.AllowDrop = $true; $tabSelecao.Add_DragEnter($acaoDragEnter); $tabSelecao.Add_DragDrop($acaoDragDrop)
$tabControl.AllowDrop = $true; $tabControl.Add_DragEnter($acaoDragEnter); $tabControl.Add_DragDrop($acaoDragDrop)

# --- RODAPÉ PROFISSIONAL ---
$global:blurAtivo = $true
$btnBlur = New-Object System.Windows.Forms.Button
$btnBlur.Location = New-Object System.Drawing.Point(20, 460)
$btnBlur.Size = New-Object System.Drawing.Size(220, 30)
$btnBlur.Text = "✨ Tema: DARK + BLUR"
$btnBlur.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$btnBlur.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnBlur.FlatAppearance.BorderSize = 1
$btnBlur.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(99, 102, 241)
$btnBlur.BackColor = [System.Drawing.Color]::FromArgb(38, 40, 58)
$btnBlur.ForeColor = [System.Drawing.Color]::FromArgb(165, 180, 252)
$btnBlur.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnBlur.Add_Click({
    $global:blurAtivo = -not $global:blurAtivo
    if ($global:blurAtivo) { Aplicar-TemaModerno } else { Aplicar-TemaClassico }
})

$lblPausa = New-Object System.Windows.Forms.Label
$lblPausa.Text = "Pausas:"
$lblPausa.Location = New-Object System.Drawing.Point(20, 506)
$lblPausa.AutoSize = $true
$lblPausa.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblPausa.ForeColor = [System.Drawing.Color]::FromArgb(220, 225, 240)

$trackPausa = New-Object System.Windows.Forms.TrackBar
$trackPausa.Location = New-Object System.Drawing.Point(75, 500)
$trackPausa.Size = New-Object System.Drawing.Size(115, 30)
$trackPausa.Minimum = 15; $trackPausa.Maximum = 50; $trackPausa.Value = [Math]::Min([Math]::Max(15, [int]$cfg.Pausa), 50); $trackPausa.TickFrequency = 5
$lblPausaVal = New-Object System.Windows.Forms.Label
$lblPausaVal.Text = (($trackPausa.Value / 10.0).ToString("0.0") + "s"); $lblPausaVal.Location = New-Object System.Drawing.Point(195, 506); $lblPausaVal.AutoSize = $true
$lblPausaVal.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblPausaVal.ForeColor = [System.Drawing.Color]::FromArgb(129, 140, 248)
$trackPausa.Add_ValueChanged({ $lblPausaVal.Text = (($trackPausa.Value / 10.0).ToString("0.0") + "s") })

$lblOpacidade = New-Object System.Windows.Forms.Label
$lblOpacidade.Text = "Opacidade:"
$lblOpacidade.Location = New-Object System.Drawing.Point(20, 548)
$lblOpacidade.AutoSize = $true
$lblOpacidade.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblOpacidade.ForeColor = [System.Drawing.Color]::FromArgb(220, 225, 240)

$trackOpacidade = New-Object System.Windows.Forms.TrackBar
$trackOpacidade.Location = New-Object System.Drawing.Point(85, 542)
$trackOpacidade.Size = New-Object System.Drawing.Size(105, 30)
$trackOpacidade.Minimum = 80; $trackOpacidade.Maximum = 100; $trackOpacidade.Value = 98; $trackOpacidade.TickFrequency = 5
$lblOpacidadeVal = New-Object System.Windows.Forms.Label
$lblOpacidadeVal.Text = "98%"; $lblOpacidadeVal.Location = New-Object System.Drawing.Point(195, 548); $lblOpacidadeVal.AutoSize = $true
$lblOpacidadeVal.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblOpacidadeVal.ForeColor = [System.Drawing.Color]::FromArgb(129, 140, 248)
$trackOpacidade.Add_ValueChanged({
    $form.Opacity = ($trackOpacidade.Value / 100.0)
    $lblOpacidadeVal.Text = "$($trackOpacidade.Value)%"
})

$btnCancelar = New-Object System.Windows.Forms.Button
$btnCancelar.Text = "Fechar"
$btnCancelar.Location = New-Object System.Drawing.Point(250, 498)
$btnCancelar.Size = New-Object System.Drawing.Size(95, 74)
$btnCancelar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnCancelar.FlatAppearance.BorderSize = 1
$btnCancelar.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(75, 85, 99)
$btnCancelar.BackColor = [System.Drawing.Color]::FromArgb(38, 41, 54)
$btnCancelar.ForeColor = [System.Drawing.Color]::FromArgb(220, 225, 235)
$btnCancelar.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnCancelar.Cursor = [System.Windows.Forms.Cursors]::Hand
$global:procPipeline = $null
$btnCancelar.Add_Click({
    if ($global:procPipeline) {
        # Durante o processamento o botao cancela; o que ja ficou pronto e mantido (checkpoint)
        $global:cancelarPipeline = $true
        $btnCancelar.Text = "Cancelando..."
    } else {
        $form.Close()
    }
})
$form.Controls.Add($btnCancelar)

$btnIniciar = New-Object System.Windows.Forms.Button
$btnIniciar.Location = New-Object System.Drawing.Point(355, 498)
$btnIniciar.Size = New-Object System.Drawing.Size(240, 74)
$btnIniciar.Text = "▶ INICIAR PROCESSAMENTO"
$btnIniciar.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnIniciar.ForeColor = [System.Drawing.Color]::White
$btnIniciar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnIniciar.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnIniciar.Add_MouseEnter({ $btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(52, 211, 153) })
$btnIniciar.Add_MouseLeave({ $btnIniciar.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129) })

$btnIniciar.Add_Click({
    $global:encoderEscolhido =$cmbEncoder.SelectedIndex
    if ($trackPausa) {
        $global:limitePausa = ($trackPausa.Value / 10.0).ToString('0.0', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    $global:videosSelecionados = @()
    foreach ($item in $chkListVideos.CheckedItems) {
        if ($global:mapaVideos.ContainsKey($item)) {$global:videosSelecionados += $global:mapaVideos[$item]
        } else {
            $global:videosSelecionados += $item
        }
    }

    if ($global:videosSelecionados.Count -eq 0) {         [System.Windows.Forms.MessageBox]::Show($form, "Selecione ou arraste pelo menos um vídeo para a lista antes de iniciar.", "Aviso", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)
        return
    }

    $btnIniciar.Enabled = $false; $btnIniciar.Text = [char]0x23F3 + " PROCESSANDO..."
    $btnCancelar.Text = "Cancelar"
    Atualizar-ProgressoUI 2 "Iniciando esteira de processamento..."

    try {
        Executar-MotorPipeline
    } catch {
        [void][System.Windows.Forms.MessageBox]::Show($form, "Erro inesperado: $($_.Exception.Message)", "Erro",
            [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    } finally {
        $global:procPipeline = $null
        $btnIniciar.Enabled = $true; $btnIniciar.Text = [char]0x25B6 + " INICIAR PROCESSAMENTO"
        $btnCancelar.Text = "Fechar"
    }
})

$form.ClientSize = New-Object System.Drawing.Size(615, 630)

$global:pbarProgresso = New-Object System.Windows.Forms.ProgressBar
$global:pbarProgresso.Location = New-Object System.Drawing.Point(20, 582); $global:pbarProgresso.Size = New-Object System.Drawing.Size(575, 12)
$global:pbarProgresso.Style = [System.Windows.Forms.ProgressBarStyle]::Continuous; $global:pbarProgresso.Value = 0
$form.Controls.Add($global:pbarProgresso)

$global:lblStatusProgresso = New-Object System.Windows.Forms.Label
$global:lblStatusProgresso.Location = New-Object System.Drawing.Point(20, 598)
$global:lblStatusProgresso.Size = New-Object System.Drawing.Size(575, 22); $global:lblStatusProgresso.Text = "Status: Pronto para iniciar."
$global:lblStatusProgresso.ForeColor = [System.Drawing.Color]::FromArgb(200, 200, 200)
$global:lblStatusProgresso.BackColor = [System.Drawing.Color]::Transparent; $global:lblStatusProgresso.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$form.Controls.Add($global:lblStatusProgresso)

function Global:Atualizar-ProgressoUI([int]$pct, [string]$texto) {
    try {
        $global:pbarProgresso.Value = [Math]::Min(100, [Math]::Max(0,$pct))
        $global:lblStatusProgresso.Text = "Status: " + $texto
        $global:pbarProgresso.Refresh(); $global:lblStatusProgresso.Refresh()
        [System.Windows.Forms.Application]::DoEvents()
    } catch { }
}
$form.Controls.Add($btnIniciar)

$form.Controls.AddRange(@($btnBlur, $lblPausa, $trackPausa, $lblPausaVal, $lblOpacidade, $trackOpacidade, $lblOpacidadeVal))

# Abre a janela diretamente estilizada
$form.Add_Shown({
    Aplicar-TemaModerno
    $form.ClientSize = New-Object System.Drawing.Size(620, 620)
    $form.Activate()
})



function Global:Encontrar-Motor {
    # Ordem: executavel empacotado > ambiente virtual (instalar.ps1) > launcher py > python do PATH
    $exe = Join-Path $raiz "motor\luismedia.exe"
    if (Test-Path -LiteralPath $exe) { return @($exe) }
    $venv = Join-Path $raiz ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) { return @($venv, "-m", "luismedia") }
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3", "-m", "luismedia") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python", "-m", "luismedia") }
    return $null
}

function Global:Montar-Perfil {
    $encoders = @("auto", "h264_amf", "libx264", "h264_nvenc", "h264_qsv")
    $usarIA = $chkIA.Checked -or $chkCortes.Checked
    return [ordered]@{
        profile_name = "gui"
        autocut = [ordered]@{
            enabled = $chkAutoCut.Checked
            export_edl = $chkEDL.Checked
            keep_pauses_longer_than_s = [double]($trackPausa.Value / 10.0)
        }
        audio = [ordered]@{ master = $chkAudioBroadcast.Checked; target_lufs = -14 }
        render = [ordered]@{ encoder = $encoders[[Math]::Max(0, $cmbEncoder.SelectedIndex)]; hardsub = $chkHardsubHoriz.Checked }
        slides = [ordered]@{ enabled = $chkSlides.Checked; handout = $true; handout_pdf = $chkPDF.Checked }
        llm = [ordered]@{
            enabled = $usarIA
            summary = ($chkIA.Checked -and $chkResumo.Checked)
            quiz = ($chkIA.Checked -and $chkQuiz.Checked)
            clips = $chkCortes.Checked
            clips_count = [int]$numCortes.Value
        }
        output = [ordered]@{ chapters = $true; zip_package = $true }
    }
}

function Global:Nome-Etapa([string]$etapa) {
    $nomes = @{
        autocut = "Cortando pausas"; audio = "Extraindo audio"; transcricao = "Transcrevendo (Whisper)"
        masterizacao = "Masterizando voz"; hardsub = "Queimando legenda"; ia = "IA local"
        resumo = "Gerando resumo"; quiz = "Gerando quiz"; cortes = "Gerando cortes 9:16"
        slides = "Detectando slides"; apostila = "Montando apostila"; validacao = "Validando video"
    }
    if ($nomes.ContainsKey($etapa)) { return $nomes[$etapa] }
    return $etapa
}

function Global:Parar-Processo($proc) {
    if ($proc -and -not $proc.HasExited) {
        # Mata a arvore inteira (python + ffmpeg filhos), sem deixar processo zumbi
        & taskkill /F /T /PID $proc.Id 2>$null | Out-Null
    }
}

function Global:Executar-MotorPipeline {
    $global:cancelarPipeline = $false

    if ([string]::IsNullOrWhiteSpace($txtDestino.Text)) {
        $txtDestino.Text = Join-Path $raiz "saida\$nomeAula"
    }
    $dirSaida = $txtDestino.Text.Trim()
    if (-not (Test-Path -LiteralPath $dirSaida)) {
        [void](New-Item -Path $dirSaida -ItemType Directory -Force)
    }

    # Salva as escolhas da interface para a proxima vez
    $novoCfg = [ordered]@{
        PresetIndex = $cmbPresets.SelectedIndex; AutoCut = $chkAutoCut.Checked; EDL = $chkEDL.Checked
        Audio = $chkAudioBroadcast.Checked; Hardsub = $chkHardsubHoriz.Checked; Slides = $chkSlides.Checked
        PDF = $chkPDF.Checked; IA = $chkIA.Checked; Resumo = $chkResumo.Checked; Quiz = $chkQuiz.Checked
        Cortes = $chkCortes.Checked; QtdCortes = [int]$numCortes.Value; Encoder = $cmbEncoder.SelectedIndex
        Pausa = $trackPausa.Value
    }
    try { $novoCfg | ConvertTo-Json | Set-Content -LiteralPath $configFile -Encoding UTF8 } catch { }

    $motor = Encontrar-Motor
    if (-not $motor) {
        [void][System.Windows.Forms.MessageBox]::Show($form,
            "Motor nao encontrado.`n`nRode o instalar.ps1 (na pasta do LUIS MEDIA TOOLS) uma vez e tente de novo.",
            "Instalacao incompleta", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
        return
    }
    $pyExe = $motor[0]
    $pyPre = @(); if ($motor.Count -gt 1) { $pyPre = $motor[1..($motor.Count - 1)] }

    # Confere se o motor esta instalado antes de comecar
    & $pyExe @pyPre --version *> $null
    if ($LASTEXITCODE -ne 0) {
        [void][System.Windows.Forms.MessageBox]::Show($form,
            "O motor LUIS MEDIA (luismedia) nao esta instalado neste Python.`n`nRode o instalar.ps1 uma vez e tente de novo.",
            "Instalacao incompleta", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
        return
    }

    $perfilPath = Join-Path ([System.IO.Path]::GetTempPath()) ("luismedia-perfil-{0}.json" -f [guid]::NewGuid().ToString("N"))
    $json = (Montar-Perfil) | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($perfilPath, $json, (New-Object System.Text.UTF8Encoding($false)))

    function Citar([string]$s) { return '"' + ($s -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"' }
    $argsLista = @($pyPre) + @("--profile", $perfilPath, "run")
    $argsLista += $global:videosSelecionados
    $argsLista += @("-o", $dirSaida, "--json-events")

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pyExe
    $psi.Arguments = (($argsLista | ForEach-Object { Citar ([string]$_) }) -join " ")
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8"
    $psi.EnvironmentVariables["PYTHONUTF8"] = "1"

    Write-Host "`n[START] $($global:videosSelecionados.Count) video(s) -> $dirSaida" -ForegroundColor Cyan
    $proc = [System.Diagnostics.Process]::Start($psi)
    $global:procPipeline = $proc
    $erroTask = $proc.StandardError.ReadToEndAsync()   # le o stderr em paralelo (evita travar o buffer)
    $linhaTask = $proc.StandardOutput.ReadLineAsync()

    # Laco de leitura que mantem a janela responsiva (DoEvents a cada 50 ms)
    while ($true) {
        if ($global:cancelarPipeline) { Parar-Processo $proc; break }
        if ($linhaTask.IsCompleted) {
            $linha = $linhaTask.Result
            if ($null -eq $linha) { break }   # fim do stdout
            if ($linha.StartsWith("{")) {
                try {
                    $evt = $linha | ConvertFrom-Json
                    $total = [Math]::Max(1, [int]$evt.total)
                    $idx = [Math]::Max(1, [int]$evt.index)
                    # Progresso geral = videos anteriores + fracao das etapas deste video
                    $ordem = @("validacao", "autocut", "audio", "transcricao", "masterizacao", "hardsub", "ia", "resumo", "quiz", "cortes", "slides", "apostila")
                    $pos = [Math]::Max(0, [array]::IndexOf($ordem, [string]$evt.stage))
                    $fracao = ($pos + [Math]::Min(1.0, [double]$evt.progress)) / $ordem.Count
                    $pct = [int](100 * (($idx - 1) + $fracao) / $total)
                    $txt = "[{0}/{1}] {2} - {3}" -f $idx, $total, $evt.video, (Nome-Etapa $evt.stage)
                    if ($evt.status -eq "running" -and [double]$evt.progress -gt 0) { $txt += (" ({0:P0})" -f [double]$evt.progress) }
                    if ($evt.status -eq "failed") { $txt += " - FALHOU: " + $evt.message; Write-Host "    [ERRO] $($evt.stage): $($evt.message)" -ForegroundColor Red }
                    elseif ($evt.status -eq "done") { Write-Host "    [OK] $($evt.video) - $(Nome-Etapa $evt.stage)" -ForegroundColor Green }
                    Atualizar-ProgressoUI $pct $txt
                } catch { }
            } else {
                Write-Host $linha
            }
            $linhaTask = $proc.StandardOutput.ReadLineAsync()
        } else {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 50
        }
    }
    if (-not $proc.HasExited) { [void]$proc.WaitForExit(10000) }
    $global:procPipeline = $null
    Remove-Item -LiteralPath $perfilPath -Force -ErrorAction SilentlyContinue

    $logErro = $erroTask.Result
    if ($logErro) { Write-Host $logErro -ForegroundColor DarkGray }

    if ($global:cancelarPipeline) {
        Atualizar-ProgressoUI 0 "Cancelado. O que ja ficou pronto foi mantido; rodar de novo continua de onde parou."
        return
    }

    # Relatorio honesto: le o que cada video realmente gerou
    $relatorio = Join-Path $dirSaida "relatorio.json"
    $ok = 0; $falhas = @(); $avisos = 0
    if (Test-Path -LiteralPath $relatorio) {
        $itens = Get-Content -LiteralPath $relatorio -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($r in $itens) {
            if ($r.ok) { $ok++ } else { $falhas += ("- {0}: {1}" -f [System.IO.Path]::GetFileName($r.source), $r.error) }
            $avisos += @($r.warnings).Count
        }
    }

    Atualizar-ProgressoUI 100 ("Concluido: {0} ok, {1} com falha." -f $ok, $falhas.Count)
    try { [System.Console]::Beep(1000, 300); [System.Console]::Beep(1500, 400) } catch { }

    if ($falhas.Count -eq 0 -and $ok -gt 0) {
        $msg = "$ok video(s) processado(s) com sucesso."
        if ($avisos -gt 0) { $msg += "`n$avisos aviso(s): veja relatorio.json na pasta de saida." }
        $icone = [System.Windows.Forms.MessageBoxIcon]::Information
    } else {
        $msg = "$ok video(s) ok e $($falhas.Count) com falha:`n`n" + ($falhas -join "`n")
        if ($falhas.Count -eq 0) { $msg = "Nada foi processado. Veja o log (job.log.jsonl) na pasta de saida.`n`n$logErro" }
        $icone = [System.Windows.Forms.MessageBoxIcon]::Warning
    }
    [void][System.Windows.Forms.MessageBox]::Show($form, $msg, "Resultado", [System.Windows.Forms.MessageBoxButtons]::OK, $icone)
    Start-Process explorer.exe -ArgumentList ('"{0}"' -f $dirSaida)
}

# Fecha o processo do motor se a janela for fechada no meio
$form.Add_FormClosing({ if ($global:procPipeline) { $global:cancelarPipeline = $true; Parar-Processo $global:procPipeline } })

[void]$form.ShowDialog()
