# Changelog

## [1.5.2] - 2026-11-23

### Corrigido
- **Legendas aparecendo antes da voz em vídeos com música ou ruído de fundo.** O encaixe agora
  usa um detector de voz (Silero, o mesmo que o Whisper usa por dentro) em vez do volume: mede
  quanto o Whisper está adiantado na aula toda, corrige todas as legendas e ainda empurra cada
  começo de frase até onde a voz começa. Os cortes de pausas e vícios andam junto.
- Vídeos já transcritos são corrigidos sozinhos ao abrir em **Revisar e editar** (com Ctrl+Z e
  aviso na tela); o botão "Encaixar no início da fala" também usa o detector novo.

## [1.5.1] - 2026-11-23

### Corrigido
- **Legendas adiantadas em vídeos cujo áudio começa depois da imagem** (comum em vídeos de
  celular, OBS e exportados de editores): o áudio era extraído sem esse atraso inicial e todas as
  legendas saíam adiantadas pelo mesmo tanto. Agora o áudio é extraído alinhado com a imagem.
- Resultados de versões anteriores são consertados sozinhos (uma vez): ao abrir o vídeo em
  Revisar e editar ou ao processar de novo, legendas, cortes e transcrição são empurrados pelo
  atraso do arquivo, sem refazer a transcrição.

## [1.5.0] - 2026-11-23

### Novo
- **Editar pelo texto:** na revisão, a transcrição vira um documento. Clique numa palavra para ir
  até ela; selecione e aperte Delete para tirar o trecho do vídeo; o que vai sair aparece riscado
  e pode ser restaurado. A palavra falada fica destacada enquanto o vídeo toca.
- **Regravações saem sozinhas:** quando a frase é começada e repetida ("a função… não, a função
  quadrática é…"), a primeira tentativa vira corte e fica só a última. Casos duvidosos vêm
  desmarcados. Botão "Procurar regravações" para vídeos já processados.
- **Relatório do professor** (`documentos/Relatorio-do-Professor.html`): palavras por minuto ao
  longo da aula, vícios e palavras-muleta, regravações, perguntas para a turma, tempo economizado,
  notas de ritmo, fluência, clareza e engajamento, e dicas para a próxima gravação (com a IA local,
  quando o Ollama está aberto). Resumo e botão na tela Início.

## [1.4.1] - 2026-11-22

### Corrigido
- **Legenda adiantada em relação à fala:** o Whisper costuma marcar o início da frase alguns
  décimos antes da voz. Agora o início de cada legenda (e das palavras do destaque) é encaixado
  onde o volume do áudio realmente sobe.

### Novo
- **Ritmo da legenda:** Rápido (blocos curtos que trocam junto com a fala), Padrão ou Devagar
  (mais tempo para ler). Na tela Início, em Processar em lote e na revisão, onde refaz as
  legendas do vídeo aberto mantendo as correções de texto.
- **Sincronia manual** na revisão (−0,1 s / +0,1 s em todas as legendas) e botão
  "Encaixar no início da fala" para vídeos já processados. Tudo com Ctrl+Z.

## [1.4.0] - 2026-11-22

### Novo: editar sem precisar de outro programa
- **Tela Início de um passo:** arraste o vídeo, escolha o estilo da legenda e clique em **Gerar**.
  Opções avançadas ficam em "Processar em lote".
- **Corte de pausas e vícios:** depois da transcrição o app encontra pausas longas e hesitações
  ("é…", "ãh", "hum") pelas palavras do Whisper, confere no áudio se a pausa é silêncio mesmo e
  sugere os cortes. "Né" e "tipo" vêm desmarcados. Pausas longas (demonstração) são mantidas.
  O vídeo final sai sem os trechos (`<nome>_EDITADO.mp4` + EDL) e as legendas, cortes 9:16 e
  apostila acompanham os novos tempos.
- **Linha do tempo na revisão:** onda do áudio, cortes clicáveis, blocos de legenda para arrastar
  e puxar as bordas, seleção de trecho para cortar à mão, prévia que pula os cortes.
- **Desfazer e refazer** (Ctrl+Z / Ctrl+Y) e atalhos: Espaço/K tocar, J/L ±3 s, ←/→ legenda,
  Delete corta a seleção.

### Mudou
- O corte de silêncio antigo (antes da transcrição) foi substituído pela limpeza revisável.

## [1.3.0] - 2026-11-22

### Novo: painel de estilo profissional com player
- **Player na prévia:** botão ▶ reproduz 4 s da legenda animada (entrada, palavra falada,
  emojis) em loop, desenhada pelo mesmo motor do vídeo final.
- **Linha do tempo:** escolha qualquer momento do vídeo; a prévia mostra aquele quadro exato.
- **Legendas reais na prévia:** ao abrir um vídeo em **Revisar legendas**, a prévia passa a usar
  o texto, os tempos e as palavras-chave dele.
- **Painel minimalista:** inspetor com seções (Texto, Cores, Caixa, Posição, Animação, Extras),
  só os campos que fazem sentido aparecem; opções de modelo no menu ⋯; salvar no topo.

## [1.2.0] - 2026-11-22

### Novo: legendas estilo CapCut
- **Novas animações de entrada:** quicar (bounce), deslizar de baixo e máquina de escrever.
- **Caixa colorida na palavra falada** (efeito marca-texto), só atrás da palavra do momento.
- **Palavras-chave destacadas pela IA:** o Ollama escolhe os termos importantes da aula, que
  ganham cor e tamanho próprios. Somam-se ao vocabulário e dá para editar em **Revisar legendas**.
- **Emojis automáticos** (🔥💡✅💰⏰📚…) acima da legenda quando ela fala do assunto, também nos cortes.
- **Gradiente** no texto e **duas cores alternadas** entre legendas.
- **Modelos próprios:** salve o estilo com um nome, exclua, exporte e importe (`.estilo.json`)
  para usar em outro computador ou mandar para clientes.
- **Posição livre:** arraste a legenda na prévia para colocá-la onde quiser.
- Novos modelos prontos: Marca-texto, Gradiente fogo, Duas cores, Máquina de escrever.

## [1.1.2] - 2026-11-22

### Corrigido
- A transcricao falhava com "open() got an unexpected keyword argument 'metadata_errors'":
  o faster-whisper usa uma opcao que o PyAV 14+ removeu. O app agora le o audio sozinho e
  entrega ao Whisper ja decodificado.
- O build do instalador passou a rodar uma transcricao real com o Whisper no Windows.

## [1.1.1] - 2026-11-11

### Corrigido
- O botão **Iniciar processamento** não fazia nada na versão 1.1.0 (o clique gerava um erro
  que ficava escondido porque o app roda sem console).

### Melhorado
- Qualquer erro inesperado agora aparece numa mensagem na tela e é salvo em `erros.log`, na
  pasta de dados do app (`%LOCALAPPDATA%\LuisMediaTools`).
- Os testes do app clicam nos botões como o usuário.

## [1.1.0] - 2026-11-11

### Novo: legendas profissionais
- **Velocidade de leitura:** cada legenda fica na tela o tempo necessário para ler a até
  17 caracteres por segundo (padrão profissional), sem invadir a próxima. Configurável.
- **Intervalo de 2 quadros** (~0,083 s) entre legendas, para o olho perceber a troca.
- **Revisar antes de queimar:** a tela **Revisar legendas** mostra o vídeo, a lista de legendas
  com tempo e caracteres por segundo (alerta quando está rápida demais), edição de texto e
  tempo, rebalancear linhas, juntar, excluir, localizar e substituir em todas. "Aprovar e gerar
  vídeos" continua o processamento sem transcrever de novo.
- **Correções automáticas** (ex.: "wisper = Whisper"), aplicadas em toda aula nova. Dá para
  adicionar direto do editor ("Lembrar para as próximas aulas") ou em Configurações.
- **Vocabulário da aula:** nomes, siglas e termos vão para o Whisper (contexto + hotwords) e
  ele acerta a grafia na primeira vez.
- **Estilos estilo CapCut:** fonte (Poppins, Anton, Bebas Neue, Archivo Black embutidas, além
  das do sistema), tamanho, cor, contorno, sombra, brilho neon, caixa de fundo, posição,
  animação de entrada (fade, pop), palavras por legenda e **destaque da palavra falada**
  (cor, cor + pop, karaokê revelando palavra por palavra). Modelos prontos para a aula (16:9)
  e para os cortes (CapCut amarelo, Destaque verde, Karaokê, Caixa minimal, Neon).
- **Prévia real** na tela de estilos: desenhada pelo mesmo motor (libass) que gera o vídeo.

### Melhorado
- Checkpoint por etapa: mudar o estilo da legenda refaz só a legenda e o vídeo legendado, sem
  transcrever de novo; editar o texto refaz legendas, vídeo legendado, cortes e apostila.
- Cortes 9:16 usam as legendas revisadas e o estilo vertical; apostila usa o texto revisado.
- O instalador pode ser publicado pela aba Actions ("Run workflow" com "publicar").

## [1.0.1] - 2026-11-11

### Novo
- **Instalador `Setup.exe`** (Inno Setup), gerado automaticamente pelo GitHub Actions: app,
  Python e FFmpeg embutidos, sem precisar de administrador, com atalhos, desinstalador em
  "Adicionar ou remover programas" e link opcional para o Ollama.
- Publicação automática na página Releases ao criar uma tag `v*`.
- `--selftest` no app, usado no build para confirmar que o executável abre e acha o FFmpeg embutido.

### Corrigido
- O Ollama aberto pelo `instalar.ps1` ficava preso à pasta do programa e impedia apagá-la.

## [1.0.0] - 2026-11-11

### Novo
- **App desktop** (PySide6/Qt), que abre direto numa janela, sem terminal:
  - Processar aulas: fila com arrastar e soltar, duração de cada vídeo, modos prontos e
    personalizado, progresso por vídeo e etapa, cancelamento imediato e resumo final.
  - Slides com IA: roteiro gerado pelo Ollama, editor e apresentação 16:9 interativa.
  - Diagnóstico com explicação de como resolver e download do modelo de IA com progresso.
  - Configurações salvas por usuário (Whisper, Ollama, qualidade, volume, ZIP).
- Instalador cria o atalho **LUIS MEDIA TOOLS** na Área de Trabalho e no Menu Iniciar.
- Versão portátil gera também `LUIS MEDIA TOOLS.exe` (janela, com ícone próprio).
- Cancelar interrompe na hora o FFmpeg e a transcrição em andamento.
- `--profile` aceita o nome do modo (`--profile redes-sociais`).

### Corrigido
- Janelas de console piscando a cada chamada do FFmpeg quando o app roda sem console.

## [0.9.1] - 2026-11-11

### Corrigido
- Scripts bloqueados pelo Windows ("is not digitally signed") quando o projeto vem de um
  ZIP baixado: o instalador agora libera os arquivos.
- O instalador não baixa o modelo de IA de novo se ele já estiver instalado.

### Novo
- Atalhos de dois cliques: `Instalar.cmd`, `Abrir LUIS MEDIA TOOLS.cmd` e `Menu LUIS MEDIA TOOLS.cmd`.

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
- CI no GitHub Actions (Windows, Linux, macOS) com 45 testes e checagem dos .ps1.

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
