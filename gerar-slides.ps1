param(
    [Parameter(Mandatory=$false)]
    [string]$ArquivoRoteiro
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$PastaScript = Split-Path -Parent $MyInvocation.MyCommand.Path
$PastaSlides = Join-Path $PastaScript "slides"

if (-not (Test-Path $PastaSlides)) {
    New-Item -ItemType Directory -Path $PastaSlides -Force | Out-Null
}

Clear-Host
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "     ESTUDIO EDITORIAL DE SLIDES - LUIS MEDIA TOOLS      " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

if ([string]::IsNullOrWhiteSpace($ArquivoRoteiro)) {
    $ArquivoRoteiro = Join-Path $PastaSlides "roteiro-aula.md"
}

$utf8SemBom = [System.Text.UTF8Encoding]::new($false)

# Cria arquivo modelo se nao existir
if (-not (Test-Path $ArquivoRoteiro)) {
    $linhasExemplo = @(
        "# Aula 01: Apresentacao Pessoal em Ingles",
        "### Curso de Ingles Pratico",
        "**Professor Luis**",
        "",
        "[NOTA] Comece se apresentando com energia e explicando a dinamica.",
        "",
        "---",
        "",
        "# O que voce vai aprender hoje?",
        "",
        "- Como falar seu **nome** e **idade**",
        "- Como dizer de **onde voce e**",
        "- Como falar sobre sua **profissao**",
        "- Expressar gostos simples",
        "",
        "---",
        "",
        "# Estrutura de Frases",
        "",
        "|| COLUNA",
        "### Perguntas",
        "- What is your name?",
        "- Where are you from?",
        "|| COLUNA",
        "### Respostas",
        "- My name is Luis.",
        "- I am from Brazil.",
        "|| FIM",
        "",
        "[DICA] No dia a dia, 'What is' vira a contracao 'What''s'.",
        "",
        "---",
        "",
        "# Exemplo de Codigo",
        "",
        "```bash",
        "git commit -m 'feat: modulo de slides'",
        "git push origin main",
        "```",
        "",
        "[ATENCAO] Pratique a fala das sentencas de forma natural.",
        "",
        "---",
        "",
        "# Resumo da Aula",
        "",
        "- Dominamos a estrutura basica de introducao.",
        "- Na proxima aula: **dialogos reais e situacoes de viagem**."
    )
    [System.IO.File]::WriteAllLines($ArquivoRoteiro, $linhasExemplo, $utf8SemBom)
    Write-Host "[INFO] Arquivo modelo criado em: $ArquivoRoteiro" -ForegroundColor Yellow
}

Write-Host "Compilando apresentacao Pro a partir de: $ArquivoRoteiro" -ForegroundColor Cyan

$linhasMd = [System.IO.File]::ReadAllLines($ArquivoRoteiro, [System.Text.Encoding]::UTF8)
$slidesRaw = ($linhasMd -join "`n") -split "(?m)^---`s*$"

$slidesHtml = @()
$numSlide = 1

foreach ($slideTexto in $slidesRaw) {
    $linhas = $slideTexto.Trim() -split "`n"
    $corpoHtml = @()
    $emLista =$false
    $emCodigo =$false
    $notasSlide = @()
    $emColunas =$false

    foreach ($l in$linhas) {
        $t =$l.TrimEnd()

        if ($t -match '^```') {
            if ($emCodigo) {
                $corpoHtml += "</code></pre>"
                $emCodigo = $false
            } else {
                if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
                $corpoHtml += "<pre class='code-block'><code>"
                $emCodigo = $true
            }
            continue
        }
        if ($emCodigo) {
            $tEscaped = [System.Web.HttpUtility]::HtmlEncode($t)
            $corpoHtml += "$tEscaped"
            continue
        }

        if ($t -match '^\|\|\s*COLUNA') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            if (-not $emColunas) {
                $corpoHtml += "<div class='columns-layout'><div class='col'>"
                $emColunas = $true
            } else {
                $corpoHtml += "</div><div class='col'>"
            }
            continue
        }
        if ($t -match '^\|\|\s*FIM') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            if ($emColunas) {
                $corpoHtml += "</div></div>"
                $emColunas = $false
            }
            continue
        }

        $tTrim = $t.Trim()
        if ([string]::IsNullOrWhiteSpace($tTrim)) { continue }

        if ($tTrim -match '^\[NOTA\]\s*(.+)$') {
            $notasSlide += $Matches[1]
            continue
        }

        $tTrim = [System.Text.RegularExpressions.Regex]::Replace($tTrim, '\*\*(.*?)\*\*', '<strong>$1</strong>')
        $tTrim = [System.Text.RegularExpressions.Regex]::Replace($tTrim, '\*(.*?)\*', '<em>$1</em>')
        $tTrim = [System.Text.RegularExpressions.Regex]::Replace($tTrim, '`([^`]+)`', '<code class="inline-code">$1</code>')

        if ($tTrim -match '^\[DICA\]\s*(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<div class='callout tip'><span class='tag'>DICA</span> $($Matches[1])</div>"
        }
        elseif ($tTrim -match '^\[ATENCAO\]\s*(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<div class='callout warn'><span class='tag'>ATENCAO</span> $($Matches[1])</div>"
        }
        elseif ($tTrim -match '^#\s+(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<h1>$($Matches[1])</h1>"
        }
        elseif ($tTrim -match '^##\s+(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<h2>$($Matches[1])</h2>"
        }
        elseif ($tTrim -match '^###\s+(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<h3>$($Matches[1])</h3>"
        }
        elseif ($tTrim -match '^>\s*(.+)$') {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<blockquote>$($Matches[1])</blockquote>"
        }
        elseif ($tTrim -match '^-\s+(.+)$') {
            if (-not $emLista) { $corpoHtml += "<ul>"; $emLista = $true }
            $corpoHtml += "<li>$($Matches[1])</li>"
        }
        elseif ($tTrim -match '^\d+\.\s+(.+)$') {
            if (-not $emLista) { $corpoHtml += "<ol>"; $emLista = $true }
            $corpoHtml += "<li>$($Matches[1])</li>"
        }
        else {
            if ($emLista) { $corpoHtml += "</ul>"; $emLista = $false }
            $corpoHtml += "<p>$tTrim</p>"
        }
    }
    if ($emLista) { $corpoHtml += "</ul>" }
    if ($emColunas) { $corpoHtml += "</div></div>" }

    $notaHtml = if ($notasSlide.Count -gt 0) {
        "<div class='speaker-notes-box' style='display:none;'><div class='notes-label'>NOTA PRIVADA:</div>" + ($notasSlide -join "<br>") + "</div>"
    } else { "" }

    $conteudoSlide = $corpoHtml -join "`n"
    $classeAtiva = if ($numSlide -eq 1) { "active" } else { "" }
    $slidesHtml += "<section class='slide $classeAtiva' id='slide-$numSlide' onclick='selectSlide($($numSlide - 1))'><div class='inner'>$conteudoSlide</div>$notaHtml<div class='slide-num'>$numSlide / $($slidesRaw.Count)</div></section>"
    $numSlide++
}

$css = @"
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #090d13; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; overflow: hidden; user-select: none; }
.progress-container { position: fixed; top: 0; left: 0; width: 100%; height: 4px; background: rgba(255,255,255,0.06); z-index: 1000; }
.progress-bar { height: 100%; width: 0%; background: linear-gradient(90deg, #388bfd, #2ea043); transition: width 0.25s ease; }
.slide-deck { width: 92vw; max-width: 1500px; aspect-ratio: 16 / 9; max-height: 88vh; position: relative; background: #121820; border: 1px solid #30363d; border-radius: 14px; box-shadow: 0 25px 60px rgba(0,0,0,0.8); display: flex; overflow: hidden; }
.slide { display: none; width: 100%; height: 100%; padding: 65px 85px; flex-direction: column; justify-content: center; position: relative; }
.slide.active { display: flex; animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: scale(0.995); } to { opacity: 1; transform: scale(1); } }
h1 { font-size: 3.2rem; color: #58a6ff; margin-bottom: 22px; line-height: 1.18; font-weight: 700; }
h2 { font-size: 2.2rem; color: #7ee787; margin-bottom: 18px; }
h3 { font-size: 1.55rem; color: #8b949e; margin-bottom: 20px; font-weight: 400; }
p, li { font-size: 1.8rem; line-height: 1.6; color: #c9d1d9; margin-bottom: 12px; }
ul, ol { margin-left: 44px; margin-bottom: 20px; }
li { margin-bottom: 12px; }
strong { color: #f0883e; font-weight: 600; }
blockquote { border-left: 5px solid #58a6ff; background: rgba(88, 166, 255, 0.07); padding: 16px 24px; border-radius: 0 8px 8px 0; margin: 20px 0; font-style: italic; color: #a5d6ff; font-size: 1.8rem; }
.columns-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin: 20px 0; }
.col { display: flex; flex-direction: column; }
.code-block { background: #070a0e; border: 1px solid #30363d; border-radius: 8px; padding: 18px 22px; font-family: monospace; font-size: 1.3rem; color: #79c0ff; overflow-x: auto; margin: 18px 0; }
.inline-code { background: #21262d; color: #ff7b72; padding: 3px 8px; border-radius: 5px; font-family: monospace; font-size: 1.5rem; }
.callout { padding: 14px 20px; border-radius: 8px; margin: 16px 0; font-size: 1.55rem; display: flex; align-items: center; gap: 12px; }
.callout.tip { background: rgba(46, 160, 67, 0.12); border: 1px solid rgba(46, 160, 67, 0.35); color: #7ee787; }
.callout.warn { background: rgba(210, 153, 34, 0.12); border: 1px solid rgba(210, 153, 34, 0.35); color: #e3b341; }
.callout .tag { font-size: 0.85rem; font-weight: 800; padding: 4px 8px; border-radius: 5px; background: rgba(255,255,255,0.12); }
.slide-num { position: absolute; bottom: 24px; right: 32px; font-size: 1.05rem; color: #484f58; font-weight: 600; }
.top-hud { position: fixed; top: 14px; right: 24px; display: flex; gap: 12px; align-items: center; font-size: 0.9rem; color: #8b949e; z-index: 1001; font-family: monospace; }
.hud-badge { background: #161b22; border: 1px solid #30363d; padding: 4px 12px; border-radius: 20px; }
.speaker-notes-box { position: absolute; bottom: 20px; left: 80px; right: 180px; background: rgba(13, 17, 23, 0.95); border: 1px solid #f0883e; border-radius: 8px; padding: 12px 18px; color: #f0883e; font-size: 1.2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.8); z-index: 50; }
.notes-label { font-size: 0.8rem; font-weight: bold; margin-bottom: 4px; color: #8b949e; }
.hint { position: fixed; bottom: 10px; color: #484f58; font-size: 0.85rem; }
body.overview-mode { overflow-y: auto; height: auto; padding: 50px 20px; }
body.overview-mode .slide-deck { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 20px; width: 100%; max-width: 1400px; height: auto; max-height: none; background: transparent; border: none; box-shadow: none; }
body.overview-mode .slide { display: flex !important; aspect-ratio: 16 / 9; height: auto; border: 1px solid #30363d; border-radius: 8px; background: #161b22; padding: 20px; cursor: pointer; }
body.overview-mode .slide:hover { border-color: #58a6ff; }
body.overview-mode .slide.active { border-color: #2ea043; box-shadow: 0 0 15px rgba(46, 160, 67, 0.4); }
body.overview-mode .slide h1 { font-size: 1.3rem; }
body.overview-mode .slide h2 { font-size: 1.1rem; }
body.overview-mode .slide h3, body.overview-mode .slide p, body.overview-mode .slide li { font-size: 0.9rem; }
body.overview-mode .top-hud, body.overview-mode .hint, body.overview-mode .progress-container { display: none; }
@media print {
  body { background: #fff !important; color: #111 !important; height: auto !important; }
  .progress-container, .top-hud, .hint, .speaker-notes-box { display: none !important; }
  .slide-deck { width: 100% !important; border: none !important; box-shadow: none !important; background: transparent !important; display: block !important; }
  .slide { display: block !important; page-break-after: always; height: 100vh; padding: 40px; background: #fff !important; color: #111 !important; }
  h1 { color: #0969da !important; }
  h2 { color: #1a7f37 !important; }
  h3, p, li { color: #24292f !important; }
}
"@

$js = @"
let cur = 0;
const slides = document.querySelectorAll('.slide');
const bar = document.getElementById('progressBar');
const timerElem = document.getElementById('timer');
let isOverview = false;
let showNotes = false;

function update() {
  slides.forEach((s, i) => s.classList.toggle('active', i === cur));
  const pct = ((cur + 1) / slides.length) * 100;
  bar.style.width = pct + '%';
}

function next() { if (cur < slides.length - 1) { cur++; update(); } }
function prev() { if (cur > 0) { cur--; update(); } }

function toggleOverview() {
  isOverview = !isOverview;
  document.body.classList.toggle('overview-mode', isOverview);
  if (!isOverview) update();
}

function toggleNotes() {
  showNotes = !showNotes;
  document.querySelectorAll('.speaker-notes-box').forEach(box => {
    box.style.display = showNotes ? 'block' : 'none';
  });
}

function selectSlide(idx) {
  cur = idx;
  if (isOverview) toggleOverview();
  else update();
}

window.addEventListener('keydown', (e) => {
  if (isOverview && (e.key === 'Escape' || e.key.toLowerCase() === 'o')) { toggleOverview(); return; }
  if (e.key.toLowerCase() === 'o') { toggleOverview(); return; }
  if (e.key.toLowerCase() === 'n') { toggleNotes(); return; }
  if (e.key.toLowerCase() === 'p') { window.print(); return; }
  if (e.key.toLowerCase() === 'r') { sec = 0; return; }

  if (!isOverview) {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') next();
    if (e.key === 'ArrowLeft' || e.key === 'PageUp') prev();
  }
});

let sec = 0;
setInterval(() => {
  sec++;
  const m = String(Math.floor(sec / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  timerElem.textContent = m + ':' + s;
}, 1000);

update();
"@

$corpoSlides = $slidesHtml -join "`n"

$htmlFinal = @"
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LUIS MEDIA TOOLS - Apresentacao Pro</title>
<style>
$css
</style>
</head>
<body>
<div class="progress-container"><div class="progress-bar" id="progressBar"></div></div>
<div class="top-hud">
  <div class="hud-badge" id="timer">00:00</div>
  <div class="hud-badge">[O] Grade | [N] Notas</div>
</div>
<div class="slide-deck" id="deck">
$corpoSlides
</div>
<div class="hint">Navegue: [Setas / Espaco] | [O] Grade | [N] Notas | [P] PDF | [R] Timer</div>
<script>
$js
</script>
</body>
</html>
"@

$ArquivoHtml = [System.IO.Path]::ChangeExtension($ArquivoRoteiro, ".html")
[System.IO.File]::WriteAllText($ArquivoHtml, $htmlFinal, $utf8SemBom)

Write-Host "[OK] Apresentacao Editorial Pro gerada com sucesso!" -ForegroundColor Green
Write-Host "Arquivo pronto: $ArquivoHtml" -ForegroundColor Yellow
Write-Host ""
$abrir = Read-Host "Deseja abrir os slides no navegador agora? (S/N)"
if ($abrir -match '^[sSyY]$') {
    Start-Process $ArquivoHtml
}
