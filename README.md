# 🎬 LUIS MEDIA TOOLS

Ecossistema local de automação audiovisual, transcrição e geração de apresentações didáticas com inteligência artificial.

## 🚀 Funcionalidades

- **Apresentações com IA Local (Ollama / Llama 3.2):** Criação de slides didáticos em Markdown e compilação direta para HTML5 interativo (16:9) com atalhos de navegação, timer e suporte a exportação em PDF.
- **Transcrição Automatizada:** Extração de áudio e transcrição temporal com Whisper (.srt, .vtt, .ass, .json).
- **Masterização Broadcast:** Normalização de áudio para streaming no padrão -14 LUFS (EBU R128) via FFmpeg.
- **Cérebro Editorial:** Detecção automática de mudanças de cena no vídeo para extrair frames de slides e compilar apostilas ilustradas em HTML.
- **Piloto Automático:** Pipeline unificado executável com apenas um comando.

## 🛠️ Tecnologias Utilizadas

- PowerShell (Orquestração de scripts e automação)
- Python 3 (Processamento de texto, templates e chamadas ao LLM)
- FFmpeg (Tratamento de áudio e corte de vídeo)
- OpenAI Whisper (Reconhecimento de fala local)
- Ollama (Llama 3.2 para geração de roteiros)

## 💻 Como Usar

1. Gerar Apresentação:
   .\gerar-slides.ps1

2. Executar Pipeline de Produção Completo:
   Coloque os vídeos em entrada/ e execute:
   .\pipeline-completo.ps1
