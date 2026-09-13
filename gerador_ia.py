import sys
import os
import json
import urllib.request

def chamar_ollama(prompt, model="llama3.2:3b"):
    url = "http://localhost:11434/api/generate"
    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("response", "")
    except Exception as e:
        print(f"[ERRO OLLAMA] Certifique-se de que o Ollama esta aberto: {e}")
        return None

def processar_aula(dir_saida):
    pasta_legendas = os.path.join(dir_saida, "1_Legendas")
    pasta_editorial = os.path.join(dir_saida, "5_Editorial")
    pasta_docs = os.path.join(dir_saida, "6_Documentos")

    # 1. Ler todas as legendas da aula
    texto_completo = []
    if os.path.exists(pasta_legendas):
        for arq in sorted(os.listdir(pasta_legendas)):
            if arq.endswith(".srt"):
                with open(os.path.join(pasta_legendas, arq), "r", encoding="utf-8", errors="ignore") as f:
                    linhas = f.readlines()
                    # Filtra apenas o texto das legendas (ignora numeros e timestamps)
                    for l in linhas:
                        l_limpa = l.strip()
                        if l_limpa and not l_limpa.isdigit() and "-->" not in l_limpa:
                            texto_completo.append(l_limpa)

    transcricao = " ".join(texto_completo)
    if not transcricao:
        print("[AVISO] Nenhuma transcricao encontrada para gerar resumo.")
        return

    # Limite prudente de contexto para CPU
    transcricao = transcricao[:12000]

    # 2. Gerar Resumo Executivo
    print("    [LLAMA] Gerando Resumo Executivo...")
    prompt_resumo = f"""Voce e um assistente pedagogico de alto nivel.
Com base na transcricao da aula abaixo, crie um Resumo Executivo bem estruturado em Markdown:
- Objetivo central da aula
- Pontos-chave explicados (em tópicos detalhados)
- Conclusão prática / próximas etapas

Transcricao da aula:
{transcricao}
"""
    resumo_md = chamar_ollama(prompt_resumo)
    if resumo_md:
        with open(os.path.join(pasta_editorial, "Resumo-Executivo.md"), "w", encoding="utf-8") as f:
            f.write(resumo_md)
        print("    [OK] Resumo-Executivo.md salvo em 5_Editorial.")

    # 3. Gerar Quiz Interativo em HTML
    print("    [LLAMA] Gerando Quiz Interativo...")
    prompt_quiz = f"""Crie um quiz interativo com 5 questoes de multipla escolha baseado na aula abaixo.
Retorne APENAS um documento HTML completo e estilizado (CSS embutido, visual escuro e moderno).
Para cada questao, inclua alternativas (A, B, C, D) e um elemento interativo simples ou gabarito explicativo com a resposta correta ao clicar ou no final.

Transcricao:
{transcricao}
"""
    quiz_html = chamar_ollama(prompt_quiz)
    if quiz_html:
        # Remove eventuais marcadores markdown que o modelo coloque
        quiz_limpo = quiz_html.replace("```html", "").replace("```", "").strip()
        with open(os.path.join(pasta_docs, "Quiz-Fixacao.html"), "w", encoding="utf-8") as f:
            f.write(quiz_limpo)
        print("    [OK] Quiz-Fixacao.html salvo em 6_Documentos.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_aula(sys.argv[1])
