# LUIS MEDIA TOOLS
Pipeline automatizado de producao audiovisual e geracao editorial.

## Modulos
- luis-media.ps1: Painel principal interativo
- pipeline-completo.ps1: Execucao automatica completa
- slides_engine.py: Compilador de slides HTML 16:9 a partir de Markdown
- editorial_engine.py: Gerador de apostila didatica ilustrada
- extrair-slides.ps1: Deteccao de cenas e extracao de frames via FFmpeg
- transcrever.ps1: Transcricao com Whisper
- normalizar-audio.ps1: Masterizacao em -14 LUFS
- juntar-audios.ps1: Concatenacao de audio
- organizar-saida.ps1: Padronizacao de pastas e saidas
- gerar-entregaveis.ps1: Relatorios, legendas ASS e arquivos ZIP

## Como Usar
1. Execute .\luis-media.ps1.
2. Use a opcao [S] para criar e apresentar slides.
3. Coloque as gravacoes brutas em entrada/.
4. Use a opcao [A] para processamento completo.
