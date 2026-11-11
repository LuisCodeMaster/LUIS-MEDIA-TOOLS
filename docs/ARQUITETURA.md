# Arquitetura

## Camadas

Cada camada só depende da camada de baixo.

| Camada | Pasta | Responsabilidade |
| --- | --- | --- |
| Interfaces | `pipeline-completo.ps1`, `src/luismedia/cli.py` | Coletar as escolhas do usuário e mostrar o progresso. Sem regra de negócio |
| Pipeline | `src/luismedia/pipeline/` | Ordem das etapas, checkpoint (`manifest.json`), eventos, relatório, ZIP |
| Stages | `src/luismedia/stages/` | Cada etapa de mídia, de IA e editorial |
| Core | `src/luismedia/core/` | Configuração, schemas, legendas, segmentação, erros, retry, logs. Python puro |
| Adapters | `src/luismedia/adapters/` | Único lugar que conversa com FFmpeg, Whisper, Ollama e o navegador |

## Contrato entre etapas

As etapas trocam objetos validados, não "pastas combinadas":

- `Transcript` (`legendas/<nome>.transcript.json`): segmentos e palavras com tempo.
- `slides/slides.json`: lista de `SlideFrame` com o instante real de cada slide.
- `manifest.json`: status e saídas de cada etapa, mais o hash da configuração. Se a
  configuração muda, tudo é refeito; se não muda, o que está pronto é reaproveitado.

## Erros

| Erro | Quando | O que o pipeline faz |
| --- | --- | --- |
| `InvalidMedia` | Arquivo corrompido, sem áudio | Reprova o vídeo antes de gastar CPU |
| `ProcessFailed` / `ProcessTimeout` | FFmpeg falhou ou travou | Mata o processo; GPU → CPU no render |
| `OutOfMemory` | Whisper sem RAM/VRAM | Degrada: CUDA fp16 → int8 → CPU → modelo menor |
| `ServiceUnavailable` | Ollama fora do ar | Retry com backoff; depois vira aviso |
| `LLMOutputInvalid` | JSON fora do schema | Reenvia o erro ao modelo (até 3 vezes) |
| `DependencyMissing` | FFmpeg, modelo ou navegador ausente | Mensagem com a ação para resolver |

Etapas essenciais (autocut, áudio, transcrição) reprovam o vídeo. As opcionais
(masterização, hardsub, IA, slides, apostila) viram aviso no `relatorio.json`.

## Progresso

O `Pipeline` emite `ProgressEvent(video, stage, status, progress, index, total)`.
A CLI imprime esses eventos (texto ou JSON Lines com `--json-events`) e a interface
gráfica lê esse JSON. Uma API REST ou um webhook futuros só precisam de mais um listener.

## Próximos passos (roadmap)

1. API REST local (FastAPI) com eventos via SSE e webhook assinado.
2. Fila com pools separados de CPU e GPU (transcrever um vídeo enquanto renderiza outro).
3. Um único render final juntando autocut e legenda.
4. Licenciamento, assistente de primeira execução na interface, atualização automática.
5. Adapter whisper.cpp (Vulkan) para acelerar o Whisper em GPUs AMD e Intel.
