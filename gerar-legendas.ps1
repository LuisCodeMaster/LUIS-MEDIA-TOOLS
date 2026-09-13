param(
    [Parameter(Mandatory=$true)]
    [string]$Json
)

$ErrorActionPreference = "Stop"

# ========================================
# CONFIGURAÇÕES
# ========================================

$MaxCharsCurta = 42
$MaxCharsShorts = 32

$MaxWordsCurta = 14
$MaxWordsShorts = 8

$DuracaoMinima = 0.8
$DuracaoMaxima = 4.0

$PausaNatural = 0.45

# ========================================
# CABEÇALHO
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     GERADOR DE LEGENDAS INTELIGENTES" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ========================================
# VERIFICAR JSON
# ========================================

if (-not (Test-Path $Json)) {
    Write-Host "ERRO: JSON nao encontrado:" -ForegroundColor Red
    Write-Host $Json
    exit 1
}

Write-Host "Arquivo JSON:" -ForegroundColor Yellow
Write-Host $Json
Write-Host ""

# ========================================
# LER JSON
# ========================================

try {
    $Dados = Get-Content -Raw -Encoding UTF8 $Json | ConvertFrom-Json
}
catch {
    Write-Host "ERRO ao ler o JSON." -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

if ($null -eq $Dados.segments) {
    Write-Host "ERRO: Nenhum segmento encontrado no JSON." -ForegroundColor Red
    exit 1
}

# ========================================
# FUNÇÃO: NORMALIZAR TEXTO
# ========================================

function Normalize-Text {
    param(
        [string]$Text
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    $Text = $Text.Trim()
    $Text = $Text -replace '\s+', ' '

    return $Text
}

# ========================================
# FUNÇÃO: FORMATAR TEMPO SRT
# ========================================

function Format-Time {
    param(
        [double]$Seconds
    )

    if ($Seconds -lt 0) {
        $Seconds = 0
    }

    $Horas = [int][math]::Floor($Seconds / 3600)
    $Minutos = [int][math]::Floor(($Seconds % 3600) / 60)
    $Segundos = [int][math]::Floor($Seconds % 60)

    $Milissegundos = [int][math]::Round(
        (($Seconds - [math]::Floor($Seconds)) * 1000),
        0
    )

    if ($Milissegundos -ge 1000) {
        $Segundos++
        $Milissegundos = 0
    }

    if ($Segundos -ge 60) {
        $Minutos++
        $Segundos = 0
    }

    if ($Minutos -ge 60) {
        $Horas++
        $Minutos = 0
    }

    $H = $Horas.ToString("00")
    $M = $Minutos.ToString("00")
    $S = $Segundos.ToString("00")
    $MS = $Milissegundos.ToString("000")

    return "$H`:$M`:$S,$MS"
}

# ========================================
# FUNÇÃO: PEGAR PALAVRAS
# ========================================

function Get-SegmentWords {
    param(
        $Segment
    )

    $Resultado = @()

    if ($null -ne $Segment.words) {

        foreach ($Word in $Segment.words) {

            if ($null -eq $Word.start -or $null -eq $Word.end) {
                continue
            }

            $Texto = Normalize-Text $Word.word

            if ([string]::IsNullOrWhiteSpace($Texto)) {
                continue
            }

            $Resultado += [PSCustomObject]@{
                Text = $Texto
                Start = [double]$Word.start
                End = [double]$Word.end
            }
        }
    }

    # Fallback para segmentos sem timestamps individuais
    if ($Resultado.Count -eq 0) {

        $Texto = Normalize-Text $Segment.text

        if (-not [string]::IsNullOrWhiteSpace($Texto)) {

            $Resultado += [PSCustomObject]@{
                Text = $Texto
                Start = [double]$Segment.start
                End = [double]$Segment.end
            }
        }
    }

    return $Resultado
}

# ========================================
# FUNÇÃO: VERIFICAR PONTUAÇÃO
# ========================================

function Ends-With-Punctuation {
    param(
        [string]$Text
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $false
    }

    return $Text.Trim() -match '[.!?…]$'
}

# ========================================
# FUNÇÃO: FORMATAR DUAS LINHAS
# ========================================

function Format-CaptionText {
    param(
        [string]$Text,
        [int]$MaxChars
    )

    $Text = Normalize-Text $Text

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    if ($Text.Length -le $MaxChars) {
        return $Text
    }

    $Words = $Text -split ' '

    if ($Words.Count -le 1) {
        return $Text
    }

    $MelhorQuebra = -1
    $MelhorScore = -999999

    for ($i = 1; $i -lt $Words.Count; $i++) {

        $Linha1 = ($Words[0..($i - 1)] -join ' ')
        $Linha2 = ($Words[$i..($Words.Count - 1)] -join ' ')

        if ($Linha1.Length -gt $MaxChars) {
            continue
        }

        if ($Linha2.Length -gt $MaxChars) {
            continue
        }

        $Diferenca = [math]::Abs(
            $Linha1.Length - $Linha2.Length
        )

        $Score = -$Diferenca

        # Preferir quebra depois de pontuação
        if ($Linha1 -match '[,.!?;:]$') {
            $Score += 30
        }

        # Evitar linha muito curta
        if ($Linha1.Length -lt 8) {
            $Score -= 10
        }

        if ($Linha2.Length -lt 8) {
            $Score -= 10
        }

        if ($Score -gt $MelhorScore) {
            $MelhorScore = $Score
            $MelhorQuebra = $i
        }
    }

    if ($MelhorQuebra -gt 0) {

        $Linha1 = ($Words[0..($MelhorQuebra - 1)] -join ' ')
        $Linha2 = ($Words[$MelhorQuebra..($Words.Count - 1)] -join ' ')

        return "$Linha1`n$Linha2"
    }

    # Fallback
    $Linha1 = ""
    $Linha2 = ""

    foreach ($Word in $Words) {

        if ([string]::IsNullOrEmpty($Linha1)) {
            $Linha1 = $Word
            continue
        }

        $Teste = "$Linha1 $Word"

        if ($Teste.Length -le $MaxChars) {
            $Linha1 = $Teste
        }
        else {
            if ([string]::IsNullOrEmpty($Linha2)) {
                $Linha2 = $Word
            }
            else {
                $Linha2 = "$Linha2 $Word"
            }
        }
    }

    if ($Linha2) {
        return "$Linha1`n$Linha2"
    }

    return $Linha1
}

# ========================================
# FUNÇÃO: CRIAR LEGENDA
# ========================================

function New-Caption {
    param(
        $Words
    )

    if ($Words.Count -eq 0) {
        return $null
    }

    $Texto = ($Words | ForEach-Object {
        $_.Text
    }) -join ' '

    $Texto = Normalize-Text $Texto

    if ([string]::IsNullOrWhiteSpace($Texto)) {
        return $null
    }

    $Inicio = [double]$Words[0].Start
    $Fim = [double]$Words[$Words.Count - 1].End

    if ($Fim -le $Inicio) {
        $Fim = $Inicio + $DuracaoMinima
    }

    return [PSCustomObject]@{
        Text = $Texto
        Start = $Inicio
        End = $Fim
    }
}

# ========================================
# FUNÇÃO: CONSTRUIR LEGENDAS
# ========================================

function Build-Captions {
    param(
        $AllWords,
        [int]$MaxChars,
        [int]$MaxWords
    )

    $Captions = @()
    $Atual = @()

    foreach ($Word in $AllWords) {

        if ($Atual.Count -eq 0) {
            $Atual += $Word
            continue
        }

        $TextoAtual = ($Atual | ForEach-Object {
            $_.Text
        }) -join ' '

        $Teste = "$TextoAtual $($Word.Text)"

        $Duracao = [double]$Word.End - [double]$Atual[0].Start

        $Pausa = [double]$Word.Start - [double]$Atual[-1].End

        $Fechar = $false

        # Muitas palavras
        if ($Atual.Count -ge $MaxWords) {
            $Fechar = $true
        }

        # Muito tempo
        if ($Duracao -ge $DuracaoMaxima) {
            $Fechar = $true
        }

        # Pausa natural
        if ($Pausa -ge $PausaNatural) {
            $Fechar = $true
        }

        # Pontuação final
        if ((Ends-With-Punctuation $Atual[-1].Text) -and
            ($Atual.Count -ge 3)) {
            $Fechar = $true
        }

        # Verificar se ainda cabe em duas linhas
        $Formatado = Format-CaptionText `
            $Teste `
            $MaxChars

        $NumeroLinhas = ($Formatado -split "`n").Count

        if ($NumeroLinhas -gt 2) {
            $Fechar = $true
        }

        # Verificar limite absoluto de caracteres
        foreach ($Linha in ($Formatado -split "`n")) {
            if ($Linha.Length -gt $MaxChars) {
                $Fechar = $true
            }
        }

        if ($Fechar) {

            $Caption = New-Caption $Atual

            if ($null -ne $Caption) {
                $Captions += $Caption
            }

            $Atual = @($Word)
        }
        else {
            $Atual += $Word
        }
    }

    # Última legenda
    if ($Atual.Count -gt 0) {

        $Caption = New-Caption $Atual

        if ($null -ne $Caption) {
            $Captions += $Caption
        }
    }

    return $Captions
}

# ========================================
# FUNÇÃO: AJUSTAR DURAÇÕES
# ========================================

function Optimize-Durations {
    param(
        $Captions
    )

    for ($i = 0; $i -lt $Captions.Count; $i++) {

        $Atual = $Captions[$i]

        $Duracao = $Atual.End - $Atual.Start

        # Duração mínima
        if ($Duracao -lt $DuracaoMinima) {

            $NovoFim = $Atual.Start + $DuracaoMinima

            if ($i -lt ($Captions.Count - 1)) {

                $ProximoInicio = $Captions[$i + 1].Start

                if ($NovoFim -gt $ProximoInicio) {
                    $NovoFim = $ProximoInicio
                }
            }

            if ($NovoFim -gt $Atual.Start) {
                $Atual.End = $NovoFim
            }
        }

        # Nunca invadir próxima legenda
        if ($i -lt ($Captions.Count - 1)) {

            if ($Atual.End -gt $Captions[$i + 1].Start) {
                $Atual.End = $Captions[$i + 1].Start
            }
        }

        # Duração máxima
        if (($Atual.End - $Atual.Start) -gt $DuracaoMaxima) {
            $Atual.End = $Atual.Start + $DuracaoMaxima
        }
    }

    return $Captions
}

# ========================================
# FUNÇÃO: ESCREVER SRT
# ========================================

function Write-Srt {
    param(
        $Captions,
        [string]$Output,
        [int]$MaxChars
    )

    $Linhas = New-Object System.Collections.Generic.List[string]

    $Numero = 1

    foreach ($Caption in $Captions) {

        $Texto = Format-CaptionText `
            $Caption.Text `
            $MaxChars

        if ([string]::IsNullOrWhiteSpace($Texto)) {
            continue
        }

        $Linhas.Add($Numero.ToString())

        $Inicio = Format-Time $Caption.Start
        $Fim = Format-Time $Caption.End

        $Linhas.Add("$Inicio --> $Fim")

        foreach ($Linha in ($Texto -split "`n")) {
            $Linhas.Add($Linha)
        }

        $Linhas.Add("")

        $Numero++
    }

    [System.IO.File]::WriteAllLines(
        $Output,
        $Linhas,
        [System.Text.UTF8Encoding]::new($false)
    )
}

# ========================================
# EXTRAIR TODAS AS PALAVRAS
# ========================================

Write-Host "Lendo timestamps das palavras..." -ForegroundColor Yellow

$TodasPalavras = @()

foreach ($Segmento in $Dados.segments) {

    $Palavras = Get-SegmentWords $Segmento

    foreach ($Palavra in $Palavras) {
        $TodasPalavras += $Palavra
    }
}

if ($TodasPalavras.Count -eq 0) {
    Write-Host "ERRO: Nenhuma palavra encontrada." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] $($TodasPalavras.Count) palavras encontradas." -ForegroundColor Green
Write-Host ""

$JsonFull = (Resolve-Path $Json).Path
$Pasta = Split-Path $JsonFull -Parent

# ========================================
# LEGENDA CURTA
# ========================================

Write-Host "Gerando legenda curta..." -ForegroundColor Cyan

$Curta = Build-Captions `
    $TodasPalavras `
    $MaxCharsCurta `
    $MaxWordsCurta

$Curta = Optimize-Durations $Curta

$ArquivoCurta = Join-Path $Pasta "legenda-curta.srt"

Write-Srt `
    $Curta `
    $ArquivoCurta `
    $MaxCharsCurta

Write-Host "[OK] $ArquivoCurta" -ForegroundColor Green
Write-Host "     Blocos: $($Curta.Count)" -ForegroundColor DarkGray

# ========================================
# LEGENDA SHORTS
# ========================================

Write-Host "Gerando legenda para Shorts..." -ForegroundColor Cyan

$Shorts = Build-Captions `
    $TodasPalavras `
    $MaxCharsShorts `
    $MaxWordsShorts

$Shorts = Optimize-Durations $Shorts

$ArquivoShorts = Join-Path $Pasta "legenda-shorts.srt"

Write-Srt `
    $Shorts `
    $ArquivoShorts `
    $MaxCharsShorts

Write-Host "[OK] $ArquivoShorts" -ForegroundColor Green
Write-Host "     Blocos: $($Shorts.Count)" -ForegroundColor DarkGray

# ========================================
# FINAL
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "       LEGENDAS GERADAS COM SUCESSO" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Arquivos criados:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. $ArquivoCurta"
Write-Host "2. $ArquivoShorts"
Write-Host ""

Write-Host "Processamento concluido." -ForegroundColor Green
Write-Host ""