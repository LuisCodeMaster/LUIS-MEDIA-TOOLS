param(
    [Parameter(Mandatory=$true)]
    [string]$Json
)

$ErrorActionPreference = "Stop"

# ============================================================
# LUIS MEDIA TOOLS - GERADOR DE LEGENDAS v4
# Segmentação temporal baseada em timestamps de palavras
# ============================================================

$MaxCharsNormal = 42
$MaxCharsShorts = 32

$MinDuration = 0.80
$IdealMinDuration = 1.40
$IdealMaxDuration = 4.00
$HardMaxDuration = 5.00

$NaturalPause = 0.45
$StrongPause = 0.75

$WeakEndingWords = @(
    "a","o","as","os",
    "de","do","da","dos","das",
    "em","no","na","nos","nas",
    "por","para",
    "com",
    "e","ou",
    "que",
    "se",
    "um","uma",
    "me","te","se",
    "eu","você"
)

# ============================================================
# FUNÇÕES
# ============================================================

function Normalize-WordText {
    param([string]$Text)

    if ($null -eq $Text) {
        return ""
    }

    return ($Text -replace "\s+", " ").Trim()
}

function Get-WordClean {
    param([string]$Text)

    $t = Normalize-WordText $Text

    return ($t `
        -replace "^[\s]+", "" `
        -replace "[\s]+$", "")
}

function Test-StrongPunctuation {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }

    return $Text -match '[.!?…]$'
}

function Test-WeakPunctuation {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }

    return $Text -match '[,;:]$'
}

function Test-WeakEnding {
    param([string]$Text)

    $clean = ($Text -replace '[^\p{L}\p{N}]', '').ToLowerInvariant()

    if ([string]::IsNullOrWhiteSpace($clean)) {
        return $false
    }

    return $WeakEndingWords -contains $clean
}

function Get-Pause {
    param(
        [object]$Previous,
        [object]$Current
    )

    if ($null -eq $Previous -or $null -eq $Current) {
        return 0
    }

    $pause = [double]$Current.Start - [double]$Previous.End

    if ($pause -lt 0) {
        return 0
    }

    return $pause
}

function Format-Time {
    param([double]$Seconds)

    # Trabalhamos diretamente em milissegundos para evitar
    # arredondamentos ou perda de precisão do TimeSpan.
    $totalMs = [int][Math]::Round($Seconds * 1000)

    if ($totalMs -lt 0) {
        $totalMs = 0
    }

    $hours = [math]::Floor($totalMs / 3600000)
    $minutes = [math]::Floor(($totalMs % 3600000) / 60000)
    $seconds = [math]::Floor(($totalMs % 60000) / 1000)
    $ms = $totalMs % 1000

    return "{0:00}:{1:00}:{2:00},{3:000}" -f `
        $hours,
        $minutes,
        $seconds,
        $ms
}

function Join-Words {
    param([array]$Words)

    if ($null -eq $Words -or $Words.Count -eq 0) {
        return ""
    }

    $result = ""

    foreach ($word in $Words) {
        $text = Get-WordClean $word.Text

        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }

        if ([string]::IsNullOrWhiteSpace($result)) {
            $result = $text
        }
        else {
            $result += " " + $text
        }
    }

    return $result.Trim()
}

function Get-TextLength {
    param([array]$Words)

    return (Join-Words $Words).Length
}

function Get-BreakScore {
    param(
        [array]$Words,
        [int]$Index,
        [double]$Pause
    )

    if ($Index -lt 0 -or $Index -ge $Words.Count) {
        return -9999
    }

    $current = $Words[$Index]

    $score = 0

    # Pontuação
    if (Test-StrongPunctuation $current.Text) {
        $score += 100
    }
    elseif (Test-WeakPunctuation $current.Text) {
        $score += 45
    }

    # Pausas
    if ($Pause -ge $StrongPause) {
        $score += 90
    }
    elseif ($Pause -ge $NaturalPause) {
        $score += 45
    }
    elseif ($Pause -ge 0.25) {
        $score += 10
    }

    # Evitar terminar em palavras que dependem do que vem depois.
    if (Test-WeakEnding $current.Text) {
        $score -= 55
    }

    # Preferir blocos com tamanho razoável.
    $textLength = Get-TextLength $Words

    if ($textLength -ge 12 -and $textLength -le 42) {
        $score += 10
    }

    return $score
}

function New-WordObjects {
    param(
        [object]$Data
    )

    $result = @()

    foreach ($segment in $Data.segments) {

        if ($null -eq $segment.words) {
            continue
        }

        foreach ($word in $segment.words) {

            if ($null -eq $word.word) {
                continue
            }

            $text = Normalize-WordText $word.word

            if ([string]::IsNullOrWhiteSpace($text)) {
                continue
            }

            $start = [double]$word.start
            $end   = [double]$word.end

            if ($end -lt $start) {
                continue
            }

            $probability = 1.0

            if ($null -ne $word.probability) {
                $probability = [double]$word.probability
            }

            $item = [PSCustomObject]@{
                Text        = $text
                Start       = $start
                End         = $end
                Probability = $probability
            }

            $result += $item
        }
    }

    return $result
}

# ============================================================
# SEGMENTAÇÃO TEMPORAL
# ============================================================

function Build-BaseCaptions {
    param([array]$Words)

    $captions = @()

    if ($Words.Count -eq 0) {
        return @()
    }

    $current = @()

    for ($i = 0; $i -lt $Words.Count; $i++) {

        $word = $Words[$i]

        if ($current.Count -eq 0) {
            $current = @($word)
            continue
        }

        $previous = $current[$current.Count - 1]

        $pause = Get-Pause $previous $word

        $candidate = @()
        foreach ($item in $current) {
            $candidate += $item
        }
        $candidate += $word

        $candidateText = Join-Words $candidate
        $candidateDuration = [double]$word.End - [double]$current[0].Start

        $strongPause = $pause -ge $StrongPause
        $naturalPause = $pause -ge $NaturalPause

        $strongPunctuation = Test-StrongPunctuation $previous.Text
        $weakPunctuation = Test-WeakPunctuation $previous.Text

        $shouldBreak = $false

        # 1. Pontuação forte
        if ($strongPunctuation -and $candidateDuration -ge $IdealMinDuration) {
            $shouldBreak = $true
        }

        # 2. Pausa muito grande
        if ($strongPause -and $current.Count -ge 2) {
            $shouldBreak = $true
        }

        # 3. Pausa natural
        if (
            $naturalPause -and
            $current.Count -ge 3 -and
            $candidateDuration -ge $IdealMinDuration
        ) {
            if ($strongPunctuation -or $weakPunctuation) {
                $shouldBreak = $true
            }
        }

        # 4. Duração máxima
        if ($candidateDuration -gt $HardMaxDuration) {
            $shouldBreak = $true
        }

        # 5. Texto muito comprido
        if ($candidateText.Length -gt 72) {
            if ($current.Count -ge 4) {
                $shouldBreak = $true
            }
        }

        if ($shouldBreak) {

            # Evitar bloco de uma palavra por causa de pausa pequena
            if (
                $current.Count -eq 1 -and
                $pause -lt $StrongPause
            ) {
                $current += $word
                continue
            }

            $captions += [PSCustomObject]@{
                Words = @($current)
                Start = [double]$current[0].Start
                End   = [double]$current[$current.Count - 1].End
            }

            $current = @($word)
        }
        else {
            $current += $word
        }
    }

    if ($current.Count -gt 0) {
        $captions += [PSCustomObject]@{
            Words = @($current)
            Start = [double]$current[0].Start
            End   = [double]$current[$current.Count - 1].End
        }
    }

    return @($captions)
}# ============================================================
# OTIMIZAÇÃO DE BLOCOS
# ============================================================

function Optimize-Captions {
    param(
        [array]$Captions
    )

    $result = @()

    if ($Captions.Count -eq 0) {
        return @()
    }

    $current = $Captions[0]

    for ($i = 1; $i -lt $Captions.Count; $i++) {

        $next = $Captions[$i]

        $mergedWords = @()
        foreach ($item in $current.Words) {
            $mergedWords += $item
        }
        foreach ($item in $next.Words) {
            $mergedWords += $item
        }

        $mergedText = Join-Words $mergedWords
        $mergedDuration = [double]$next.End - [double]$current.Start

        $canMerge = $true

        if ($mergedDuration -gt $HardMaxDuration) {
            $canMerge = $false
        }

        if ($mergedText.Length -gt 72) {
            $canMerge = $false
        }

        if ($current.End -lt $next.Start) {
            $pause = [double]$next.Start - [double]$current.End

            if ($pause -ge $StrongPause) {
                $canMerge = $false
            }
        }

        if ($canMerge) {
            $current = [PSCustomObject]@{
                Words = @($mergedWords)
                Start = [double]$current.Start
                End   = [double]$next.End
            }
        }
        else {
            $result += [PSCustomObject]@{
                Words = @($current.Words)
                Start = [double]$current.Start
                End   = [double]$current.End
            }

            $current = $next
        }
    }

    if ($null -ne $current) {
        $result += [PSCustomObject]@{
            Words = @($current.Words)
            Start = [double]$current.Start
            End   = [double]$current.End
        }
    }

    return @($result)
}# ============================================================
# QUEBRA VISUAL EM DUAS LINHAS
# ============================================================

function Find-Best-LineBreak {
    param(
        [array]$Words,
        [int]$MaxChars
    )

    if ($Words.Count -le 1) {
        return $null
    }

    $bestIndex = -1
    $bestScore = -99999

    for ($i = 0; $i -lt ($Words.Count - 1); $i++) {

        $left = @($Words[0..$i])
        $right = @($Words[($i + 1)..($Words.Count - 1)])

        $leftText = Join-Words $left
        $rightText = Join-Words $right

        if (
            $leftText.Length -gt $MaxChars -or
            $rightText.Length -gt $MaxChars
        ) {
            continue
        }

        $pause = Get-Pause $Words[$i] $Words[$i + 1]

        $score = Get-BreakScore $Words $i $pause

        # Equilíbrio visual
        $difference =
            [Math]::Abs($leftText.Length - $rightText.Length)

        $score -= $difference * 0.7

        if ($leftText.Length -lt 8) {
            $score -= 20
        }

        if ($rightText.Length -lt 8) {
            $score -= 10
        }

        if ($score -gt $bestScore) {
            $bestScore = $score
            $bestIndex = $i
        }
    }

    if ($bestIndex -ge 0) {
        return $bestIndex
    }

    return $null
}

function Format-CaptionText {
    param(
        [array]$Words,
        [int]$MaxChars
    )

    $text = Join-Words $Words

    if ($text.Length -le $MaxChars) {
        return $text
    }

    $breakIndex = Find-Best-LineBreak $Words $MaxChars

    if ($null -ne $breakIndex) {

        $line1 = Join-Words @($Words[0..$breakIndex])
        $line2 = Join-Words @($Words[($breakIndex + 1)..($Words.Count - 1)])

        return "$line1`n$line2"
    }

    # Fallback: procurar uma divisão que não ultrapasse o limite
    for ($i = $Words.Count - 2; $i -ge 0; $i--) {

        $line1 = Join-Words @($Words[0..$i])
        $line2 = Join-Words @($Words[($i + 1)..($Words.Count - 1)])

        if (
            $line1.Length -le $MaxChars -and
            $line2.Length -le $MaxChars
        ) {
            return "$line1`n$line2"
        }
    }

    # Último recurso
    return $text
}

# ============================================================
# DIVISÃO DE BLOCO QUE NÃO CABE NO SHORTS
# ============================================================

function Split-For-Display {
    param(
        [object]$Caption,
        [int]$MaxChars
    )

    $words = @($Caption.Words)

    if ($words.Count -eq 0) {
        return @()
    }

    $text = Join-Words $words

    if ($text.Length -le ($MaxChars * 2)) {
        return @($Caption)
    }

    $parts = New-Object System.Collections.Generic.List[object]

    $current = New-Object System.Collections.Generic.List[object]

    foreach ($word in $words) {

        $candidate = New-Object System.Collections.Generic.List[object]; foreach ($item in $current) { [void]$candidate.Add($item) }; [void]$candidate.Add($word)
        $candidateText = Join-Words $candidate

        if (
            $current.Count -gt 0 -and
            $candidateText.Length -gt ($MaxChars * 2)
        ) {

            $parts.Add(
                [PSCustomObject]@{
                    Words = @($current)
                    Start = [double]$current[0].Start
                    End   = [double]$current[$current.Count - 1].End
                }
            )

            $current = New-Object System.Collections.Generic.List[object]
        }

        $current.Add($word)
    }

    if ($current.Count -gt 0) {

        $parts.Add(
            [PSCustomObject]@{
                Words = @($current)
                Start = [double]$current[0].Start
                End   = [double]$current[$current.Count - 1].End
            }
        )
    }

    return @($parts)
}

# ============================================================
# ESCREVER SRT
# ============================================================

function Write-Srt {
    param(
        [array]$Captions,
        [int]$MaxChars,
        [string]$OutputPath
    )

    $lines = New-Object System.Collections.Generic.List[string]

    $number = 1

    foreach ($caption in $Captions) {

        $text = Format-CaptionText `
            -Words $caption.Words `
            -MaxChars $MaxChars

        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }

        $start = Format-Time ([double]$caption.Start)
        $end   = Format-Time ([double]$caption.End)

        $lines.Add([string]$number)
        $lines.Add("$start --> $end")
        $lines.Add($text)
        $lines.Add("")

        $number++
    }

    [System.IO.File]::WriteAllLines(
        $OutputPath,
        $lines,
        [System.Text.UTF8Encoding]::new($false)
    )

    return ($number - 1)
}

# ============================================================
# MAIN
# ============================================================

Write-Host ""
Write-Host "==============================================="
Write-Host "       LUIS MEDIA TOOLS - LEGENDAS v4"
Write-Host "==============================================="
Write-Host ""

if (-not (Test-Path $Json)) {
    throw "Arquivo JSON não encontrado: $Json"
}

Write-Host "[1/6] Lendo JSON..."

$dados = Get-Content `
    -LiteralPath $Json `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json

Write-Host "[2/6] Extraindo timestamps das palavras..."

$palavras = New-WordObjects $dados

Write-Host "      $($palavras.Count) palavras encontradas"

if ($palavras.Count -eq 0) {
    throw "Nenhuma palavra com timestamp foi encontrada no JSON."
}

Write-Host "[3/6] Criando segmentação temporal natural..."

$base = Build-BaseCaptions $palavras

Write-Host "      $($base.Count) blocos iniciais"

Write-Host "[4/6] Otimizando blocos..."

$base = Optimize-Captions $base

Write-Host "      $($base.Count) blocos após otimização"

Write-Host "[5/6] Gerando versões Normal e Shorts..."

$normalPath = Join-Path `
    (Split-Path $Json -Parent) `
    "legenda-curta.srt"

$shortsPath = Join-Path `
    (Split-Path $Json -Parent) `
    "legenda-shorts.srt"

# Normal
$normalCount = Write-Srt `
    -Captions $base `
    -MaxChars $MaxCharsNormal `
    -OutputPath $normalPath

# Shorts
$shortsBase = New-Object System.Collections.Generic.List[object]

foreach ($caption in $base) {

    $parts = Split-For-Display `
        -Caption $caption `
        -MaxChars $MaxCharsShorts

    foreach ($part in $parts) {
        $shortsBase.Add($part)
    }
}

$shortsCount = Write-Srt `
    -Captions @($shortsBase) `
    -MaxChars $MaxCharsShorts `
    -OutputPath $shortsPath

Write-Host "[6/6] Concluído!"
Write-Host ""

Write-Host "Legenda normal : $normalCount blocos"
Write-Host "Legenda Shorts : $shortsCount blocos"
Write-Host ""

Write-Host "Arquivos:"
Write-Host "  $normalPath"
Write-Host "  $shortsPath"
Write-Host ""




