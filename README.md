# LUIS MEDIA TOOLS

Aplicativo desktop de pós-produção de aulas em vídeo com IA **100% local**. Você arrasta os vídeos brutos para a janela e recebe:
o vídeo sem as pausas, as legendas, o áudio no padrão do YouTube, a apostila ilustrada em PDF,
um quiz de fixação e cortes verticais prontos para Reels, Shorts e TikTok.

Nada sai do seu computador: a transcrição usa o Whisper e a IA usa o Ollama, ambos locais.

[![CI](https://github.com/LuisCodeMaster/LUIS-MEDIA-TOOLS/actions/workflows/ci.yml/badge.svg)](https://github.com/LuisCodeMaster/LUIS-MEDIA-TOOLS/actions/workflows/ci.yml)

## O que ele faz

| Recurso | Resultado |
| --- | --- |
| **Autocut** | Remove as pausas curtas e mantém as pausas didáticas longas. Exporta uma timeline EDL para DaVinci Resolve ou Premiere |
| **Legendas profissionais** | SRT, VTT e ASS em até 2 linhas de 42 caracteres, até 17 caracteres por segundo, 2 quadros entre legendas, sem cortar frases em "de", "que" ou "para". Inclui versão Shorts |
| **Revisão** | Editor com o vídeo para corrigir texto e tempo antes de gerar o vídeo legendado, com localizar e substituir e correções automáticas para as próximas aulas |
| **Vocabulário da aula** | Nomes, siglas e termos passados ao Whisper para ele acertar a grafia |
| **Estilos estilo CapCut** | Fontes, cores, contorno, caixa, neon, posição, animação e destaque da palavra falada (karaokê), com prévia real e modelos prontos |
| **Masterização de voz** | Equalização e loudness em duas passadas, no alvo de **-14 LUFS** (padrão de YouTube e Spotify) |
| **Slides e apostila** | Detecta cada troca de slide com o instante exato e monta uma apostila em HTML e PDF com o slide e o que foi falado sobre ele |
| **Resumo e quiz (IA)** | Resumo executivo em Markdown e quiz interativo em HTML com placar |
| **Cortes 9:16 (IA)** | A IA escolhe os trechos mais fortes e gera vídeos 1080x1920 com fundo desfocado e legenda grande |
| **Entregáveis** | Capítulos do YouTube, `Entregavel.zip` e um relatório do que deu certo em cada vídeo |

Os vídeos originais **nunca são movidos nem apagados**. Se o processamento parar no meio
(queda de energia, cancelamento), basta rodar de novo: ele continua de onde parou.

## Instalação (Windows)

### Pelo instalador (recomendado)

1. Baixe o `LUIS-MEDIA-TOOLS-Setup-<versão>.exe` na página
   [Releases](https://github.com/LuisCodeMaster/LUIS-MEDIA-TOOLS/releases).
2. Dê dois cliques e siga o assistente. Não precisa ser administrador, e o Python e o FFmpeg
   já vêm dentro do instalador.
3. Abra o **LUIS MEDIA TOOLS** pelo Menu Iniciar ou pela Área de Trabalho.

Para os recursos de IA (resumo, quiz, cortes e slides), instale também o
[Ollama](https://ollama.com/download). O instalador oferece o link no final. Depois abra a tela
**Diagnóstico** do app e clique em **Baixar modelo de IA**. O modelo do Whisper é baixado
sozinho na primeira transcrição.

### A partir do código (desenvolvimento)

1. Baixe o projeto (botão **Code → Download ZIP**) e extraia numa pasta fixa, por exemplo `C:\LUIS-MEDIA-TOOLS`.
2. Dê dois cliques em **`Instalar.cmd`**. Se o Windows mostrar um aviso de segurança, clique
   em **Executar**.
3. Abra o app pelo atalho **LUIS MEDIA TOOLS** na Área de Trabalho ou no Menu Iniciar.

O instalador libera os scripts que o Windows bloqueia em arquivos baixados, confere o Python 3.10+, cria um ambiente isolado (`.venv`), instala o motor e o
Whisper, oferece instalar o FFmpeg e o Ollama via `winget` e baixa o modelo de IA
(`llama3.2:3b`, cerca de 2 GB). No fim ele roda um diagnóstico.

A IA é opcional. Sem o Ollama, tudo funciona, exceto resumo, quiz e cortes 9:16, que aparecem
como aviso no relatório.

## Como usar

### App desktop

A janela tem seis telas:

- **Processar aulas:** arraste vídeos ou pastas, escolha o modo (Curso completo, Foco em redes
  sociais, Pré-edição para DaVinci/Premiere ou Personalizado), ajuste as opções e clique em
  **Iniciar**. A tabela mostra a etapa de cada vídeo, **Cancelar** para na hora sem perder o
  que já ficou pronto, e no fim aparece o resumo com o botão **Abrir pasta de saída**.
- **Revisar legendas:** vídeo + lista de legendas com alerta de leitura rápida; corrija texto e
  tempo, rebalanceie linhas e use localizar e substituir. "Aprovar e gerar vídeos" continua de
  onde parou, sem transcrever de novo.
- **Estilo das legendas:** modelos prontos e todos os ajustes (fonte, cores, contorno, caixa,
  neon, posição, animação, palavras por legenda, destaque da palavra falada) para a aula 16:9
  e para os cortes 9:16, com prévia desenhada pelo mesmo motor que gera o vídeo.
- **Slides com IA:** escreva o tema, a IA monta o roteiro, você ajusta o texto e gera uma
  apresentação 16:9 interativa (laser, desenho, notas, visão geral, exportar PDF).
- **Diagnóstico:** confere FFmpeg, placa de vídeo, Whisper, Ollama e navegador, explica como
  resolver o que faltar e baixa o modelo de IA com um clique.
- **Configurações:** modelo e idioma do Whisper, modelo do Ollama, qualidade do vídeo, volume
  alvo e o que entra no ZIP.

A janela antiga em PowerShell (`pipeline-completo.ps1`) e o menu (`luis-media.ps1`)
continuam disponíveis.

### Linha de comando (Windows, Linux e macOS)

```bash
luismedia doctor                                    # confere FFmpeg, GPU, Whisper, Ollama e navegador
luismedia run aula1.mp4 aula2.mp4 -o saida/         # processa com o perfil padrao
luismedia --profile redes-sociais run entrada/Aula1 -o saida/
luismedia --profile meu-perfil.yaml config          # mostra a configuracao final validada
```

`run --json-events` emite o progresso em JSON Lines, que é o que a interface gráfica usa.

### Perfis

Perfis prontos em `src/luismedia/profiles/` (na linha de comando, use só o nome: `--profile redes-sociais`):

- `curso-completo.yaml`: tudo ativado.
- `redes-sociais.yaml`: vídeo enxuto, legenda queimada e 5 cortes 9:16. Sem apostila.
- `pre-edicao-nle.yaml`: autocut, EDL e legendas, sem IA, para terminar no editor.

Qualquer opção pode ser ajustada. Uma chave escrita errado gera erro claro em vez de ser
ignorada. Também dá para sobrescrever por variável de ambiente, por exemplo
`LUISMEDIA_LLM__MODEL=qwen2.5:3b`. Veja todas as opções em
[`src/luismedia/core/config.py`](src/luismedia/core/config.py).

## Estrutura da saída

```text
saida/
├── capitulos-youtube.txt      # capítulos somando os vídeos do lote
├── Entregavel.zip             # legendas, áudio, slides e documentos (sem os vídeos)
├── relatorio.json             # o que funcionou, avisos e falhas por vídeo
├── job.log.jsonl              # log detalhado (para suporte)
└── aula 01/
    ├── aula 01_DINAMICO.mp4   # sem pausas
    ├── aula 01_LEGENDADO.mp4  # com legenda queimada
    ├── aula 01.edl            # timeline para o editor
    ├── legendas/              # .srt .vtt .ass, _shorts.srt, transcript.json
    ├── audio/                 # bruto e masterizado (-14 LUFS)
    ├── slides/                # frames + slides.json com o instante de cada um
    ├── documentos/            # Apostila.html/.pdf, Resumo-Executivo.md, Quiz-Fixacao.html
    └── cortes/                # vídeos 9:16
```

## Requisitos

- Windows 10/11. O app e o motor (CLI) também rodam em Linux e macOS.
- Python 3.10+ (o `instalar.ps1` cuida disso) e FFmpeg.
- 8 GB de RAM recomendados. Uma GPU NVIDIA acelera o Whisper. Placas AMD, NVIDIA e Intel
  aceleram a codificação do vídeo, e o modo **Automático** testa a placa e escolhe sozinho.
- Ollama, opcional, para os recursos de IA.
- Edge ou Chrome para gerar o PDF da apostila (o Edge já vem no Windows).

## Arquitetura

```text
Interfaces (app Qt, CLI, GUI PowerShell)  ->  Pipeline (etapas, checkpoint, eventos)
                                  ->  Core (config, schemas, legendas, erros)
                                  ->  Adapters (FFmpeg, Whisper, Ollama, PDF)
```

Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

Os scripts `.ps1` do menu (opções 1 a 9) e os `.py` da raiz são a versão anterior. Eles
continuam disponíveis e corrigidos enquanto a migração para o motor novo termina.

## Desenvolvimento

```bash
python -m pip install -e ".[dev]"
ruff check src tests
pytest -q            # 68 testes; os de integração geram vídeos sintéticos com o FFmpeg
```

O instalador `Setup.exe` é gerado pelo GitHub Actions (`.github/workflows/release.yml`). Para
publicar uma versão, crie uma tag: `git tag v1.0.0 && git push origin v1.0.0`. O instalador
aparece em Releases. Para gerar localmente uma versão portátil com o app, a CLI e o FFmpeg:

```powershell
.\packaging\build-windows.ps1 -FFmpegDir C:\ffmpeg\bin
```

## Licença

Copyright (c) 2026 LuisCodeMaster. Todos os direitos reservados. Veja [LICENSE](LICENSE) e os
componentes de terceiros em [THIRD_PARTY.md](THIRD_PARTY.md).
