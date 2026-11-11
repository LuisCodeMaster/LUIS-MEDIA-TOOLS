param(
    [Parameter(Mandatory = $true)]
    [string]$Json
)

$MaxCharsNormal = 42
$MaxCharsShorts = 32

$MinDuration = 0.80
$IdealMinDuration = 1.30
$IdealMaxDuration = 4.00
$HardMaxDuration = 5.20

$NaturalPause = 0.40
$StrongPause = 0.70

function Normalize-WordText {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    return $Text.Trim()
}

function Get-WordClean {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }
    $t = $Text.Normalize([System.Text.NormalizationForm]::FormD)
    $sb = New-Object System.Text.StringBuilder
    foreach ($c in $t.ToCharArray()) {
        if ([System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($c) -ne [System.Globalization.UnicodeCategory]::NonSpacingMark) {
            [void]$sb.Append($c)
        }
    }
    $clean = $sb.ToString().ToLower()
    return ($clean -replace '[^a-z0-9]', '')
}

function Test-StrongPunctuation {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    return ($Text -match '[\.\?\!]$')
}

function Test-WeakPunctuation {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    return ($Text -match '[\,\;\:]$')
}

function Test-WeakEnding {
    param([string]$Text)
    $clean = Get-WordClean $Text
    $weakWords = @("de", "da", "do", "das", "dos", "e", "que", "para", "pra", "com", "em", "um", "uma", "a", "o", "as", "os", "sua", "seu", "suas", "seus", "voce", "onde", "depois", "seja", "vai", "i", "my")
    return ($weakWords -contains $clean)
}

function Get-Pause {
    param($Word1, $Word2)
    if ($null -eq $Word1 -or $null -eq $Word2) { return 0.0 }
    $diff = [double]$Word2.Start - [double]$Word1.End
    if ($diff -lt 0) { return 0.0 }
    return $diff
}

function Format-Time {
    param([double]$Seconds)
    $ts = [timespan]::FromSeconds($Seconds)
    $hours = [int]$ts.Hours
    $minutes = [int]$ts.Minutes
    $secs = [int]$ts.Seconds
    $millis = [int]$ts.Milliseconds
    return ("{0:D2}:{1:D2}:{2:D2},{3:D3}" -f $hours, $minutes, $secs, $millis)
}

function Join-Words {
    param([array]$Words)
    if ($null -eq $Words -or $Words.Count -eq 0) { return "" }
    $list = @()
    foreach ($w in $Words) {
        if ($null -ne $w.Text -and -not [string]::IsNullOrWhiteSpace($w.Text)) {
            $list += $w.Text
        }
    }
    return ($list -join " ")
}

function New-WordObjects {
    param([object]$Data)

    $result = @()
    foreach ($segment in $Data.segments) {
        if ($null -eq $segment.words) { continue }
        foreach ($word in $segment.words) {
            if ($null -eq $word.word) { continue }
            $text = Normalize-WordText $word.word
            if ([string]::IsNullOrWhiteSpace($text)) { continue }

            $start = [double]$word.start
            $end = [double]$word.end
            if ($end -lt $start) { continue }

            $prob = 1.0
            if ($null -ne $word.probability) { $prob = [double]$word.probability }

            $result += [PSCustomObject]@{
                Text        = $text
                Start       = $start
                End         = $end
                Probability = $prob
            }
        }
    }
    return $result
}

function Build-BaseCaptions {
    param([array]$Words)

    $captions = @()
    if ($Words.Count -eq 0) { return @() }
    
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
        foreach ($item in $current) { $candidate += $item }
        $candidate += $word

        $candidateText = Join-Words $candidate
        $candidateDuration = [double]$word.End - [double]$current[0].Start

        $strongPause = $pause -ge $StrongPause
        $naturalPause = $pause -ge $NaturalPause

        $strongPunctuation = Test-StrongPunctuation $previous.Text
        $weakPunctuation = Test-WeakPunctuation $previous.Text

        $cleanWord = Get-WordClean $word.Text
        $prevClean = Get-WordClean $previous.Text

        $nextWordClean = ""
        if (($i + 1) -lt $Words.Count) {
            $nextWordClean = Get-WordClean $Words[$i + 1].Text
        }

        $shouldBreak = $false

        # Fim de sentença rígido (. ? !)
        if ($strongPunctuation) {
            $shouldBreak = $true
        }

        # Pausa acústica clara
        if ($strongPause -and $current.Count -ge 2) {
            $shouldBreak = $true
        }

        # Quebra equilibrada em vírgula assim que atinge 2.5s (evita arrastar até estourar 5s)
        if ($weakPunctuation -and $candidateDuration -ge 2.5 -and $current.Count -ge 3) {
            $shouldBreak = $true
        }

        # Quebra natural antes de oração conectiva / temporal
        if (($cleanWord -eq "depois" -or ($cleanWord -eq "e" -and $nextWordClean -eq "depois")) -and $candidateDuration -ge 1.8 -and $current.Count -ge 3) {
            $shouldBreak = $true
        }

        # Limites máximos de segurança
        if ($candidateDuration -gt $HardMaxDuration) {
            $shouldBreak = $true
        }
        if ($candidateText.Length -gt 72 -and $current.Count -ge 4) {
            $shouldBreak = $true
        }

        # TRAVAS SEMÂNTICAS: Impede quebras no meio de expressões conhecidas
        if ($shouldBreak) {
            # "voce e"
            if ($cleanWord -eq "e" -and $prevClean -eq "voce") { $shouldBreak = $false }
            # "I am from"
            if ($prevClean -eq "am" -and $cleanWord -eq "from") { $shouldBreak = $false }
            if ($prevClean -eq "i" -and $cleanWord -eq "am") { $shouldBreak = $false }
            # "years old" / "is old"
            if ($cleanWord -eq "old") { $shouldBreak = $false }
            # "my name is"
            if ($prevClean -eq "name" -and $cleanWord -eq "is") { $shouldBreak = $false }
            # Palavras fracas no fim da linha
            if (Test-WeakEnding $previous.Text -and $candidateDuration -lt 5.8) { $shouldBreak = $false }
        }

        if ($shouldBreak) {
            if ($current.Count -eq 1 -and $pause -lt $StrongPause) {
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
}

function Optimize-Captions {
    param([array]$Captions)

    $result = @()
    if ($Captions.Count -eq 0) { return @() }

    $current = $Captions[0]

    for ($i = 1; $i -lt $Captions.Count; $i++) {
        $next = $Captions[$i]

        $mergedWords = @()
        foreach ($item in $current.Words) { $mergedWords += $item }
        foreach ($item in $next.Words) { $mergedWords += $item }

        $mergedText = Join-Words $mergedWords
        $mergedDuration = [double]$next.End - [double]$current.Start
        $nextDuration = [double]$next.End - [double]$next.Start
        $canMerge = $true

        if ($mergedDuration -gt $HardMaxDuration) { $canMerge = $false }
        if ($mergedText.Length -gt 74) { $canMerge = $false }

        if ($current.End -lt $next.Start) {
            $pause = [double]$next.Start - [double]$current.End
            if ($pause -ge $StrongPause) { $canMerge = $false }
        }

        $lastWordCurrent = $current.Words[$current.Words.Count - 1]
        if (Test-StrongPunctuation $lastWordCurrent.Text) {
            $canMerge = $false
        }

        if ($next.Words.Count -ge 1) {
            $w0 = Get-WordClean $next.Words[0].Text
            if ($w0 -eq "depois") { $canMerge = $false }
            if ($next.Words.Count -ge 2 -and $w0 -eq "e" -and (Get-WordClean $next.Words[1].Text) -eq "depois") {
                $canMerge = $false
            }
        }

        # FUSÃO FORÇADA DE FRAGMENTOS RESIDUAIS (elimina blocos de até 3 palavras ou < 1.1s)
        if (-not $canMerge -and ($next.Words.Count -le 3 -or $nextDuration -lt 1.1) -and $mergedDuration -le 6.2 -and $mergedText.Length -le 78) {
            $canMerge = $true
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
}

function Split-For-Display {
    param(
        [object]$Caption,
        [int]$MaxChars
    )

    $words = @($Caption.Words)
    if ($words.Count -eq 0) { return @() }

    $text = Join-Words $words
    $maxLen = $MaxChars * 2

    if ($text.Length -le $maxLen) {
        return @($Caption)
    }

    $midIndex = [math]::Floor($words.Count / 2)
    $bestIndex = -1
    $bestScore = 9999

    for ($i = 1; $i -lt ($words.Count - 1); $i++) {
        if (Test-WeakEnding $words[$i].Text) { continue }
        
        $currentClean = Get-WordClean $words[$i].Text
        $nextClean = Get-WordClean $words[$i + 1].Text
        if ($nextClean -eq "e" -and $currentClean -eq "voce") { continue }
        if ($currentClean -eq "am" -and $nextClean -eq "from") { continue }

        $dist = [math]::Abs($i - $midIndex)
        $score = $dist

        if (Test-WeakPunctuation $words[$i].Text) {
            $score -= 35
        }

        if ($score -lt $bestScore) {
            $bestScore = $score
            $bestIndex = $i
        }
    }

    if ($bestIndex -eq -1) {
        $bestIndex = $midIndex
    }

    $part1 = @()
    for ($i = 0; $i -le $bestIndex; $i++) { $part1 += $words[$i] }

    $part2 = @()
    for ($i = $bestIndex + 1; $i -lt $words.Count; $i++) { $part2 += $words[$i] }

    $parts = @()
    if ($part1.Count -gt 0) {
        $parts += [PSCustomObject]@{
            Words = @($part1)
            Start = [double]$part1[0].Start
            End   = [double]$part1[$part1.Count - 1].End
        }
    }
    if ($part2.Count -gt 0) {
        $parts += [PSCustomObject]@{
            Words = @($part2)
            Start = [double]$part2[0].Start
            End   = [double]$part2[$part2.Count - 1].End
        }
    }

    return @($parts)
}

function Format-CaptionText {
    param(
        [array]$Words,
        [int]$MaxChars
    )

    $fullText = Join-Words $Words
    
    if ($fullText.Length -le $MaxChars -or $Words.Count -le 1) {
        return $fullText
    }

    $bestIndex = -1
    $bestScore = 99999

    for ($i = 0; $i -lt ($Words.Count - 1); $i++) {
        $leftPart = @()
        for ($k = 0; $k -le $i; $k++) { $leftPart += $Words[$k] }
        $leftText = Join-Words $leftPart

        $rightPart = @()
        for ($k = $i + 1; $k -lt $Words.Count; $k++) { $rightPart += $Words[$k] }
        $rightText = Join-Words $rightPart

        $overflowPenalty = 0
        if ($leftText.Length -gt $MaxChars) { $overflowPenalty += ($leftText.Length - $MaxChars) * 20 }
        if ($rightText.Length -gt $MaxChars) { $overflowPenalty += ($rightText.Length - $MaxChars) * 20 }

        $imbalance = [math]::Abs($leftText.Length - $rightText.Length)
        $score = $imbalance + $overflowPenalty

        $wordText = $Words[$i].Text
        if (Test-WeakPunctuation $wordText -and $leftText.Length -ge 8) {
            $score -= 20
        }
        if (Test-WeakEnding $wordText) {
            $score += 35
        }

        if ($score -lt $bestScore) {
            $bestScore = $score
            $bestIndex = $i
        }
    }

    if ($bestIndex -eq -1) {
        $bestIndex = [math]::Floor($Words.Count / 2)
    }

    $line1 = @()
    for ($i = 0; $i -le $bestIndex; $i++) { $line1 += $Words[$i] }

    $line2 = @()
    for ($i = $bestIndex + 1; $i -lt $Words.Count; $i++) { $line2 += $Words[$i] }

    $str1 = Join-Words $line1
    $str2 = Join-Words $line2

    return "$str1`r`n$str2"
}

function Write-Srt {
    param(
        [array]$Captions,
        [int]$MaxChars,
        [string]$OutputPath
    )

    $lines = @()
    $number = 1

    foreach ($caption in $Captions) {
        $text = Format-CaptionText -Words $caption.Words -MaxChars $MaxChars

        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }

        $start = Format-Time ([double]$caption.Start)
        $end   = Format-Time ([double]$caption.End)

        $lines += [string]$number
        $lines += [string]"$start --> $end"
        $lines += [string]$text
        $lines += [string]""

        $number++
    }

    $outputDir = Split-Path $OutputPath -Parent
    if (-not (Test-Path $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }

    [System.IO.File]::WriteAllLines(
        $OutputPath,
        [string[]]$lines,
        [System.Text.UTF8Encoding]::new($false)
    )

    return ($number - 1)
}

Write-Host "==============================================="
Write-Host "       LUIS MEDIA TOOLS - LEGENDAS v4.2"
Write-Host "==============================================="
Write-Host ""

if (-not (Test-Path $Json)) {
    Write-Error "Arquivo JSON nao encontrado: $Json"
    exit 1
}

$jsonFullPath = (Resolve-Path $Json).Path
$outputDir = Split-Path $jsonFullPath -Parent

Write-Host "[1/6] Lendo JSON..."
$rawJson = Get-Content $jsonFullPath -Raw -Encoding UTF8
$data = $rawJson | ConvertFrom-Json

Write-Host "[2/6] Extraindo timestamps das palavras..."
$words = New-WordObjects $data
Write-Host "      $($words.Count) palavras encontradas"

Write-Host "[3/6] Criando segmentacao temporal natural..."
$baseCaptions = Build-BaseCaptions $words
Write-Host "      $($baseCaptions.Count) blocos iniciais"

Write-Host "[4/6] Otimizando blocos..."
$optimized = Optimize-Captions $baseCaptions
Write-Host "      $($optimized.Count) blocos apos otimizacao"

Write-Host "[5/6] Gerando versoes Normal e Shorts..."
$normalCaptions = @()
foreach ($cap in $optimized) {
    $split = Split-For-Display -Caption $cap -MaxChars $MaxCharsNormal
    foreach ($p in $split) { $normalCaptions += $p }
}

$shortsCaptions = @()
foreach ($cap in $optimized) {
    $split = Split-For-Display -Caption $cap -MaxChars $MaxCharsShorts
    foreach ($p in $split) { $shortsCaptions += $p }
}

$normalPath = Join-Path $outputDir "legenda-curta.srt"
$shortsPath = Join-Path $outputDir "legenda-shorts.srt"

$countNormal = Write-Srt -Captions $normalCaptions -MaxChars $MaxCharsNormal -OutputPath $normalPath
$countShorts = Write-Srt -Captions $shortsCaptions -MaxChars $MaxCharsShorts -OutputPath $shortsPath

Write-Host "[6/6] Concluido!"
Write-Host ""
Write-Host "Legenda normal : $countNormal blocos"
Write-Host "Legenda Shorts : $countShorts blocos"