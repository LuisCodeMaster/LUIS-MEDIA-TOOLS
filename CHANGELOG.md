# Changelog

## [0.9.0] - 2026-11-11

### Novo
- Motor `luismedia` em Python, multiplataforma (Windows, Linux, macOS), com CLI
  `run`, `doctor` e `config`.
- Perfis YAML validados: `curso-completo`, `redes-sociais`, `pre-edicao-nle`.
- Legendas com a segmentacao da v3.1 no pipeline principal (2 linhas, sem quebrar em
  palavra fraca) e versao Shorts.
- Cortes 9:16 com fundo desfocado e legenda grande, escolhidos pela IA com resposta validada.
- Apostila que junta cada slide ao que foi falado sobre ele, com resumo no topo e PDF.
- Quiz com placar; resumo de aulas longas em partes (sem descartar o fim da aula).
- Checkpoint por video: rodar de novo continua de onde parou.
- `relatorio.json`, log `job.log.jsonl`, capitulos do YouTube e `Entregavel.zip` (ZIP64).
- Encoder "Automatico" que testa NVENC, AMF e QSV antes de usar, com fallback para CPU.
- `instalar.ps1`, opcoes [D] diagnostico e [I] instalar no menu, empacotamento PyInstaller.
- CI no GitHub Actions (Windows, Linux, macOS) com 44 testes e checagem dos .ps1.

### Corrigido
- Videos originais eram movidos para a pasta de saida.
- Pastas de resultado eram apagadas depois do ZIP, mesmo com ZIP incompleto.
- Apostila saia sempre vazia (pastas e nomes de arquivo nao batiam).
- Timecode invalido `00:00:60,000` nas legendas.
- Quiz quebrava quando o resumo falhava; cortes quebravam com tempo `MM:SS`.
- Cortes usavam a legenda de outra aula.
- Codigos de saida do FFmpeg ignorados; arquivos pela metade tratados como prontos.
- `Invoke-Expression` com nome de arquivo (risco de execucao de comando).
- Chamadas ao Ollama sem timeout (podiam travar para sempre).
- Opcoes da interface ignoradas (masterizacao, resumo, quiz, quantidade de cortes).
- Mensagem de "sucesso" mesmo quando algo falhava; janela congelada durante o processamento.
- Caminho fixo `C:\Users\ferna\Desktop\LUIS-MEDIA-TOOLS`.
- Alvo de loudness inconsistente (-16 x -14 LUFS); agora -14 LUFS em duas passadas.
