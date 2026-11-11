# Componentes de terceiros

O LUIS MEDIA TOOLS usa os componentes abaixo. Eles nao fazem parte do codigo deste
repositorio e mantem as suas proprias licencas.

| Componente | Uso | Licenca |
| --- | --- | --- |
| [FFmpeg](https://ffmpeg.org/legal.html) | Audio, video, legendas | LGPL 2.1+; builds com libx264/libx265 sao GPL |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Transcricao | MIT |
| Modelos [Whisper](https://github.com/openai/whisper) | Transcricao | MIT |
| [Ollama](https://github.com/ollama/ollama) | Servidor de IA local | MIT |
| [Llama 3.2](https://www.llama.com/llama3_2/license/) | Modelo de IA padrao | Llama 3.2 Community License |
| [pydantic](https://github.com/pydantic/pydantic) | Validacao | MIT |
| [PyYAML](https://github.com/yaml/pyyaml) | Perfis | MIT |

## Atencao antes de distribuir

- **FFmpeg:** ao incluir o `ffmpeg.exe` na versao portatil, um build com libx264 obriga a
  cumprir a GPL. A alternativa e um build LGPL, em que os encoders de GPU (NVENC, AMF, QSV)
  continuam funcionando.
- **Llama 3.2:** a licenca permite uso comercial, com condicoes de atribuicao. Confira o texto
  completo da licenca antes de vender.
