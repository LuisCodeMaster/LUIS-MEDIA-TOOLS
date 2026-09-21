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

$raiz = "C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS"
$configFile = Join-Path $raiz "config_presets.json"

$cfg = @{
    PresetIndex = 0; AutoCut = $true; EDL = $true; Hardsub =$true
    Slides = $true; PDF =$true; IA = $true; Resumo =$true; Quiz = $true; Cortes =$true; QtdCortes = 3
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
    $itemAlvo = Get-Item -LiteralPath$CaminhoPasta
    if ($itemAlvo.PSIsContainer) { $dirEntrada =$itemAlvo.FullName; $nomeAula =$itemAlvo.Name }
    else { $dirEntrada =$itemAlvo.DirectoryName; $nomeAula = (Get-Item$dirEntrada).Name }
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
$chkAudioBroadcast.Text = "Masterização de Voz de Estúdio (Equalização + Compressor + R128)"; $chkAudioBroadcast.Checked = $true; $tabVideo.Controls.Add($chkAudioBroadcast)

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
    "⚡ GPU AMD (AMF - Radeon Vega / Ryzen 5600GT)",
    "🖥️ Processador CPU (x264 - Compatibilidade Total)",
    "🟢 GPU NVIDIA (NVENC - GeForce)",
    "🔷 GPU Intel (QSV - QuickSync)"
))
$cmbEncoder.SelectedIndex = 0
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
$trackPausa.Minimum = 15; $trackPausa.Maximum = 50; $trackPausa.Value = 25; $trackPausa.TickFrequency = 5
$lblPausaVal = New-Object System.Windows.Forms.Label
$lblPausaVal.Text = "2.5s"; $lblPausaVal.Location = New-Object System.Drawing.Point(195, 506); $lblPausaVal.AutoSize = $true
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
$btnCancelar.Text = "Cancelar"
$btnCancelar.Location = New-Object System.Drawing.Point(250, 498)
$btnCancelar.Size = New-Object System.Drawing.Size(95, 74)
$btnCancelar.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnCancelar.FlatAppearance.BorderSize = 1
$btnCancelar.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(75, 85, 99)
$btnCancelar.BackColor = [System.Drawing.Color]::FromArgb(38, 41, 54)
$btnCancelar.ForeColor = [System.Drawing.Color]::FromArgb(220, 225, 235)
$btnCancelar.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$btnCancelar.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnCancelar.Add_Click({ $form.Close() })
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
    $global:encoderEscolhido = $cmbEncoder.SelectedIndex
    $global:limitePausa = ($trackPausa.Value / 10.0).ToString('0.0', [System.Globalization.CultureInfo]::InvariantCulture)
    $global:videosSelecionados = @()
    foreach ($item in $chkListVideos.CheckedItems) {
        $global:videosSelecionados += $global:mapaVideos[$item.ToString()]
    }
    $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $form.Close()
})
$form.Controls.Add($btnIniciar)

$form.Controls.AddRange(@($btnBlur, $lblPausa, $trackPausa, $lblPausaVal, $lblOpacidade, $trackOpacidade, $lblOpacidadeVal))

# Abre a janela diretamente estilizada
$form.Add_Shown({
    Aplicar-TemaModerno
    $form.ClientSize = New-Object System.Drawing.Size(620, 620)
    $form.Activate()
})

$resDialog = $form.ShowDialog()
if ($resDialog -ne [System.Windows.Forms.DialogResult]::OK) {
    Write-Host "`n[CANCELADO] Execucao cancelada pelo usuario." -ForegroundColor Yellow
    exit 0
}


# Garante pasta de destino padrao caso o campo tenha ficado em branco
if ([string]::IsNullOrWhiteSpace($txtDestino.Text)) {
    $txtDestino.Text = Join-Path $raiz "saida\$nomeAula"
}
if (-not (Test-Path -LiteralPath $txtDestino.Text.Trim())) {
    [void](New-Item -Path $txtDestino.Text.Trim() -ItemType Directory -Force)
}

# [CORREÇÃO DO MOTOR]
$videos = @()
foreach ($v in $global:videosSelecionados) {
    if (Test-Path $v) {
        $videos += (Get-Item $v)
    }
}
Write-Host "`n[START] Pipeline iniciando com $($videos.Count) vídeo(s)..." -ForegroundColor Cyan

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
# 
if (-not $videos -or $videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirEntrada -Include "*.mp4","*.mkv","*.mov" -Recurse | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
} else {
    if ($videos[0].FullName) { $dirEntrada = Split-Path $videos[0].FullName -Parent }
}
if ($videos.Count -eq 0) {
    $videos = Get-ChildItem -Path $dirSaida -Include "*.mp4","*.mkv","*.mov" | Where-Object { $_.Name -notmatch "(_DINAMICO|_sem_silencio|_LEGENDADO)" } | Sort-Object Name
    if ($videos.Count -eq 0) { exit 0 }
}

$minutagemArquivo = Join-Path $pastas["6"] "capitulos-youtube.txt"
$tempoAcumulado = 0.0
$listaCapitulos = @()


# =======================================================
# FILTRO DE SELEÇÃO PROFISSIONAL
# =======================================================
if ($global:videosSelecionados -ne $null) {
    if ($global:videosSelecionados.Count -gt 0) {
        # Filtro desativado: a lista já vem validada e com caminhos absolutos do Drag & Drop
        Write-Host "`n=======================================================" -ForegroundColor Cyan
        Write-Host " [MODO SELETIVO] Processando $($videos.Count) vídeo(s):" -ForegroundColor Green
        $videos | ForEach-Object { Write-Host "   -> $($_.Name)" -ForegroundColor Green }
        Write-Host "=======================================================`n" -ForegroundColor Cyan
    } else {
        Write-Host "`n[AVISO] Nenhum vídeo marcado na aba de seleção. Operação cancelada." -ForegroundColor Red
        exit 0
    }
}
# =======================================================

foreach ($video in $videos) {
    Write-Host "`n>>> INICIANDO PROCESSAMENTO: $($video.Name) <<<" -ForegroundColor Magenta

    $nome = $video.BaseName
    $dirTempChunk = Join-Path $dirSaida $nome
    if (-not (Test-Path $dirTempChunk)) { New-Item -ItemType Directory -Path $dirTempChunk -Force | Out-Null }

    $videoAlvo = $video.FullName
    if ($fazerAutoCut) {
        $videoDinamico = Join-Path $dirSaida "${nome}_DINAMICO.mp4"
        if (-not (Test-Path $videoDinamico)) {
            & python (Join-Path $raiz "autocut_engine.py") $video.FullName $dirSaida "--limite" $global:limitePausa
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
    
# Define os parâmetros do encoder conforme a escolha do usuário na interface
$argsEncoder = switch ($global:encoderEscolhido) {
    0 { @("-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-pix_fmt", "yuv420p") }
    1 { @("-c:v", "libx264", "-preset", "faster", "-crf", "20", "-pix_fmt", "yuv420p") }
    2 { @("-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22", "-pix_fmt", "yuv420p") }
    3 { @("-c:v", "h264_qsv", "-global_quality", "22", "-pix_fmt", "yuv420p") }
    Default { @("-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-pix_fmt", "yuv420p") }
}

        if ($fazerHardsub -and (Test-Path $assFinal) -and ((Get-Item $assFinal).Length -gt 10)) {
        $videoLegendado = Join-Path $dirSaida "${nome}_DINAMICO_LEGENDADO.mp4"
        if (-not (Test-Path $videoLegendado)) {
            Write-Host "    Renderizando versao com Legenda Fluida para Aulas..." -ForegroundColor Magenta
            
            # Formata caminho para o FFmpeg escapando apenas os dois-pontos do drive (sem barra invertida no final)
            $assFormatado = $assFinal.Replace("\", "/").Replace(":", "\:")
            
            # Executa com o encoder selecionado na interface + copia de audio
            & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vf "subtitles='$assFormatado'" @argsEncoder -c:a copy $videoLegendado
            
            # Se o encoder de GPU nao gerar o arquivo, aplica fallback automatico via CPU
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path $videoLegendado)) {
                Write-Host "    [AVISO] Recorrendo ao encoder CPU (libx264)..." -ForegroundColor Yellow
                & ffmpeg -hide_banner -loglevel error -y -i $videoAlvo -vf "subtitles='$assFormatado'" -c:v libx264 -preset faster -crf 20 -c:a copy $videoLegendado
            }

            if (Test-Path $videoLegendado) {
                Write-Host "    [OK] Video legendado gerado com sucesso!" -ForegroundColor Green
            }
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




