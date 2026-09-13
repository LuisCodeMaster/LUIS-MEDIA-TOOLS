param(
    [Parameter(Mandatory=$true)]
    [string]$Json
)

$ErrorActionPreference = "Stop"

# ============================================================
# LUIS MEDIA TOOLS - GERADOR DE LEGENDAS 3.1
# ============================================================

$MaxCharsNormal = 42
$MaxCharsShorts = 32

$MinDuration = 0.8
$MaxDuration = 5.0

$NaturalPause = 0.45
$StrongPause = 0.75

$WeakWords = @(
    "a","o","as","os",
    "de","do","da","dos","das",
    "em","no","na","nos","nas",
    "por","para","com",
    "que","e","ou",
    "um","uma"
)

# ============================================================
# CAMINHO
# ============================================================

$JsonFull = (Resolve-Path $Json).Path
$Pasta = Split-Path $JsonFull -Parent

# ============================================================
# FUNÇÕES
# ============================================================

function Normalize-Text {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    $Text = $Text.Trim()
    $Text = $Text -replace "\s+", " "
    $Text = $Text -replace "\s+([,.!?;:])", '$1'

    return $Text
}

function Format-Time {
    param([double]$Seconds)

    $ts = [TimeSpan]::FromSeconds([Math]::Max(0, $Seconds))

    return "{0:00}:{1:00}:{2:00},{3:000}" -f `
        $ts.Hours,
        $ts.Minutes,
        $ts.Seconds,
        $ts.Milliseconds
}

function Get-LastWord {
    param([string]$Text)

    $Words = $Text -split "\s+"

    if ($Words.Count -eq 0) {
        return ""
    }

    return (
        $Words[-1] -replace '[^\p{L}\p{N}\-''"]', ''
    ).ToLower()
}

function Is-StrongEnd {
    param([string]$Word)

    return $Word -match '[.!?]["'']?$'
}

function Is-WeakEnd {
    param([string]$Word)

    $Clean = Get-LastWord $Word

    return $WeakWords -contains $Clean
}

# ============================================================
# PEGAR PALAVRAS
# ============================================================

function Get-Words {
    param($Data)

    $Result = @()

    foreach ($Segment in $Data.segments) {

        if ($null -eq $Segment.words) {
            continue
        }

        foreach ($Word in $Segment.words) {

            $Text = Normalize-Text $Word.word

            if ([string]::IsNullOrWhiteSpace($Text)) {
                continue
            }

            $Result += [PSCustomObject]@{
                Text = $Text
                Start = [double]$Word.start
                End = [double]$Word.end
            }
        }
    }

    return $Result
}

# ============================================================
# SEGMENTAÇÃO TEMPORAL
# ============================================================

function Build-TimedBlocks {
    param($Words)

    $Blocks = @()
    $Current = @()

    for ($i = 0; $i -lt $Words.Count; $i++) {

        $Word = $Words[$i]

        if ($Current.Count -eq 0) {
            $Current = @($Word)
            continue
        }

        $Previous = $Current[-1]

        $Pause = $Word.Start - $Previous.End

        $CandidateWords = @($Current + $Word)
        $CandidateText = Normalize-Text (
            $CandidateWords.Text -join " "
        )

        $CurrentDuration = $Word.End - $Current[0].Start

        $PreviousStrong = Is-StrongEnd $Previous.Text
        $PreviousWeak = Is-WeakEnd $Previous.Text

        $Break = $false

        # ----------------------------------------------------
        # 1. Pontuação forte
        # ----------------------------------------------------

        if ($PreviousStrong) {
            $Break = $true
        }

        # ----------------------------------------------------
        # 2. Pausa longa
        # ----------------------------------------------------

        elseif (
            $Pause -ge $StrongPause -and
            $Current.Count -ge 3
        ) {
            $Break = $true
        }

        # ----------------------------------------------------
        # 3. Pausa natural
        # ----------------------------------------------------

        elseif (
            $Pause -ge $NaturalPause -and
            $Current.Count -ge 5 -and
            -not $PreviousWeak
        ) {
            $Break = $true
        }

        # ----------------------------------------------------
        # 4. Duração máxima
        # ----------------------------------------------------

        elseif (
            $CurrentDuration -ge $MaxDuration
        ) {

            # Só quebra se não estiver terminando em palavra fraca
            if (-not $PreviousWeak) {
                $Break = $true
            }
        }

        # ----------------------------------------------------
        # 5. Texto muito grande
        # ----------------------------------------------------

        elseif (
            $CandidateText.Length -gt 72 -and
            $Current.Count -ge 6
        ) {

            if (-not $PreviousWeak) {
                $Break = $true
            }
        }

        # ----------------------------------------------------
        # Adicionar bloco
        # ----------------------------------------------------

        if ($Break) {

            $Text = Normalize-Text (
                $Current.Text -join " "
            )

            $Blocks += [PSCustomObject]@{
                Start = $Current[0].Start
                End = $Current[-1].End
                Text = $Text
            }

            $Current = @($Word)
        }
        else {
            $Current += $Word
        }
    }

    # Último bloco
    if ($Current.Count -gt 0) {

        $Text = Normalize-Text (
            $Current.Text -join " "
        )

        $Blocks += [PSCustomObject]@{
            Start = $Current[0].Start
            End = $Current[-1].End
            Text = $Text
        }
    }

    return $Blocks
}

# ============================================================
# SEPARAR BLOCO GRANDE
# ============================================================

function Split-LongBlock {
    param(
        $Block
    )

    $Words = $Block.Text -split "\s+"

    if ($Words.Count -le 1) {
        return @($Block)
    }

    $Result = @()
    $Current = @()

    for ($i = 0; $i -lt $Words.Count; $i++) {

        $WordText = $Words[$i]

        # Procurar palavra correspondente ao timestamp
        $GlobalIndex = -1

        for ($j = 0; $j -lt $BlockWords.Count; $j++) {
            if ($BlockWords[$j].Text -eq $WordText) {
                $GlobalIndex = $j
                break
            }
        }

        $Current += $WordText

        $CurrentText = Normalize-Text ($Current -join " ")

        if (
            $CurrentText.Length -ge 60 -and
            $i -lt ($Words.Count - 1)
        ) {

            $NextWord = $Words[$i + 1]

            if (
                $WordText -match '[,.!?;:]$' -or
                $CurrentText.Length -ge 70
            ) {

                $Result += [PSCustomObject]@{
                    Text = $CurrentText
                }

                $Current = @()
            }
        }
    }

    if ($Current.Count -gt 0) {

        $Result += [PSCustomObject]@{
            Text = Normalize-Text ($Current -join " ")
        }
    }

    return $Result
}

# ============================================================
# QUEBRAR UMA LEGENDA EM DUAS LINHAS
# ============================================================

function Wrap-TwoLines {
    param(
        [string]$Text,
        [int]$MaxChars
    )

    if ($Text.Length -le $MaxChars) {
        return $Text
    }

    $Words = $Text -split "\s+"

    $Best = $null
    $BestScore = -999999

    for ($i = 1; $i -lt $Words.Count; $i++) {

        $Line1 = $Words[0..($i - 1)] -join " "
        $Line2 = $Words[$i..($Words.Count - 1)] -join " "

        if ($Line1.Length -gt $MaxChars) {
            continue
        }

        if ($Line2.Length -gt $MaxChars) {
            continue
        }

        $Score = 100

        $Difference = [Math]::Abs(
            $Line1.Length - $Line2.Length
        )

        $Score -= $Difference

        if ($Line1 -match '[,;:]$') {
            $Score += 35
        }

        if ($Line1 -match '[.!?]$') {
            $Score += 60
        }

        if ($Line1.Length -lt 10) {
            $Score -= 20
        }

        if ($Line2.Length -lt 10) {
            $Score -= 20
        }

        if ($Score -gt $BestScore) {

            $BestScore = $Score

            $Best = "$Line1`n$Line2"
        }
    }

    if ($null -ne $Best) {
        return $Best
    }

    return $Text
}

# ============================================================
# AJUSTAR DURAÇÕES
# ============================================================

function Fix-Durations {
    param($Captions)

    for ($i = 0; $i -lt $Captions.Count; $i++) {

        $Current = $Captions[$i]

        # Limite máximo
        if (
            ($Current.End - $Current.Start) -gt $MaxDuration
        ) {
            $Current.End = $Current.Start + $MaxDuration
        }

        # Não invadir próxima legenda
        if ($i -lt ($Captions.Count - 1)) {

            $Next = $Captions[$i + 1]

            if ($Current.End -ge $Next.Start) {
                $Current.End = $Next.Start - 0.03
            }
        }

        # Duração mínima
        if (
            ($Current.End - $Current.Start) -lt $MinDuration
        ) {

            $DesiredEnd = $Current.Start + $MinDuration

            if ($i -lt ($Captions.Count - 1)) {

                $Next = $Captions[$i + 1]

                $DesiredEnd = [Math]::Min(
                    $DesiredEnd,
                    $Next.Start - 0.03
                )
            }

            if ($DesiredEnd -gt $Current.End) {
                $Current.End = $DesiredEnd
            }
        }
    }

    return $Captions
}

# ============================================================
# GERAR SRT
# ============================================================

function Write-Srt {
    param(
        $Captions,
        [string]$Path
    )

    $Output = New-Object System.Collections.Generic.List[string]

    $Number = 1

    foreach ($Caption in $Captions) {

        $Output.Add([string]$Number)

        $Output.Add(
            "$(Format-Time $Caption.Start) --> $(Format-Time $Caption.End)"
        )

        $Output.Add($Caption.Text)
        $Output.Add("")

        $Number++
    }

    [System.IO.File]::WriteAllLines(
        $Path,
        $Output,
        [System.Text.UTF8Encoding]::new($false)
    )
}

# ============================================================
# EXECUÇÃO
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    LUIS MEDIA TOOLS - LEGENDAS 3.1" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] Lendo JSON..." -ForegroundColor Yellow

$Dados = Get-Content `
    $JsonFull `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json

Write-Host "[2/5] Extraindo palavras..." -ForegroundColor Yellow

$Words = @(Get-Words $Dados)

Write-Host "      $($Words.Count) palavras encontradas" -ForegroundColor Green

if ($Words.Count -eq 0) {
    throw "Nenhuma palavra encontrada no JSON."
}

Write-Host "[3/5] Criando segmentação temporal..." -ForegroundColor Yellow

$TimedBlocks = @(Build-TimedBlocks $Words)

Write-Host "      $($TimedBlocks.Count) blocos temporais" -ForegroundColor Green

# ============================================================
# LEGENDA NORMAL
# ============================================================

$Normal = @()

foreach ($Block in $TimedBlocks) {

    $Duration = $Block.End - $Block.Start

    if ($Duration -gt $MaxDuration) {

        # Divisão simples por palavras
        $BlockWords = $Words |
            Where-Object {
                $_.Start -ge $Block.Start -and
                $_.End -le $Block.End
            }

        $Current = @()

        foreach ($Word in $BlockWords) {

            $Test = @($Current + $Word)

            $TestText = Normalize-Text (
                $Test.Text -join " "
            )

            if (
                $Current.Count -gt 0 -and
                $TestText.Length -gt 55
            ) {

                $Normal += [PSCustomObject]@{
                    Start = $Current[0].Start
                    End = $Current[-1].End
                    Text = Wrap-TwoLines `
                        -Text (Normalize-Text ($Current.Text -join " ")) `
                        -MaxChars $MaxCharsNormal
                }

                $Current = @($Word)
            }
            else {
                $Current += $Word
            }
        }

        if ($Current.Count -gt 0) {

            $Normal += [PSCustomObject]@{
                Start = $Current[0].Start
                End = $Current[-1].End
                Text = Wrap-TwoLines `
                    -Text (Normalize-Text ($Current.Text -join " ")) `
                    -MaxChars $MaxCharsNormal
            }
        }
    }
    else {

        $Normal += [PSCustomObject]@{
            Start = $Block.Start
            End = $Block.End
            Text = Wrap-TwoLines `
                -Text $Block.Text `
                -MaxChars $MaxCharsNormal
        }
    }
}

$Normal = @(Fix-Durations $Normal)

# ============================================================
# SHORTS
# MESMAS DIVISÕES TEMPORAIS
# ============================================================

Write-Host "[4/5] Criando versão Shorts..." -ForegroundColor Yellow

$Shorts = @()

foreach ($Caption in $Normal) {

    $Shorts += [PSCustomObject]@{
        Start = $Caption.Start
        End = $Caption.End
        Text = Wrap-TwoLines `
            -Text ($Caption.Text -replace "`n", " ") `
            -MaxChars $MaxCharsShorts
    }
}

$Shorts = @(Fix-Durations $Shorts)

# ============================================================
# SALVAR
# ============================================================

$NormalPath = Join-Path `
    $Pasta `
    "legenda-curta.srt"

$ShortsPath = Join-Path `
    $Pasta `
    "legenda-shorts.srt"

Write-Host "[5/5] Salvando arquivos..." -ForegroundColor Yellow

Write-Srt `
    -Captions $Normal `
    -Path $NormalPath

Write-Srt `
    -Captions $Shorts `
    -Path $ShortsPath

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       LEGENDAS GERADAS" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Legenda curta : $($Normal.Count) blocos"
Write-Host "Legenda Shorts: $($Shorts.Count) blocos"

Write-Host ""
Write-Host "Legenda curta:"
Write-Host $NormalPath

Write-Host ""
Write-Host "Legenda Shorts:"
Write-Host $ShortsPath

Write-Host ""