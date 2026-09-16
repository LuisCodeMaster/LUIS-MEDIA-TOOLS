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
        template_html = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Quiz Interativo</title>
    <style>
        body { background: #0f172a; color: #f8fafc; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 40px 20px; max-width: 800px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 40px; color: #38bdf8; }
        .card { background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .pergunta { font-size: 1.2em; margin-bottom: 20px; font-weight: 600; line-height: 1.5; color: #e2e8f0; }
        button { display: block; width: 100%; text-align: left; background: #334155; color: #f8fafc; padding: 16px 20px; margin-bottom: 12px; border: 1px solid #475569; border-radius: 8px; font-size: 1em; cursor: pointer; transition: all 0.2s; }
        button:hover { background: #475569; border-color: #64748b; }
    </style>
</head>
<body>
    <h1>Quiz Interativo da Aula</h1>
    {cards_gerados}
</body>
</html>'''

    prompt_quiz = f'''Com base APENAS nesta transcrição de aula: {transcricao}
Crie 5 perguntas objetivas sobre a matéria.

RESPONDA EXATAMENTE NESTE FORMATO PARA AS 5 PERGUNTAS:
PERGUNTA: [Texto da pergunta]
CERTA: [A resposta correta]
ERRADA: [Uma resposta errada]
ERRADA: [Outra resposta errada]
ERRADA: [Mais uma resposta errada]
'''
    print("    [LLAMA] Analisando matéria e montando Quiz Inteligente...")
    quiz_texto = chamar_ollama(prompt_quiz)
    
    quiz_final = ""
    if quiz_texto:
        import random
        import re
        cards_html = ""
        
        linhas = quiz_texto.split('\n')
        questoes = []
        q_atual = None
        
        for linha in linhas:
            linha = linha.strip()
            if not linha: continue
            
            # Detecta o início de uma nova pergunta ("PERGUNTA:", "1.", "**Questão 1**")
            if re.match(r'(?i)^(PERGUNTA|QUESTÃO|QUESTAO)\s*\d*:|^\d+\.\s*|\*\*Questão', linha):
                if q_atual and q_atual['certa'] and len(q_atual['erradas']) > 0:
                    questoes.append(q_atual)
                
                # Limpa os prefixos para guardar apenas o texto real da pergunta
                texto_limpo = re.sub(r'(?i)^(PERGUNTA|QUESTÃO|QUESTAO)\s*\d*:\s*|^\d+\.\s*|\*\*Questão\s*\d+\*\*\s*', '', linha).strip()
                q_atual = {'pergunta': texto_limpo, 'certa': '', 'erradas': []}
            
            elif q_atual is not None:
                if re.match(r'(?i)^CERTA:', linha):
                    q_atual['certa'] = re.sub(r'(?i)^CERTA:\s*', '', linha).strip()
                elif re.match(r'(?i)^ERRADA:', linha):
                    q_atual['erradas'].append(re.sub(r'(?i)^ERRADA:\s*', '', linha).strip())
                elif not q_atual['pergunta']:
                    # Caso a IA tenha colocado a pergunta na linha de baixo
                    q_atual['pergunta'] = linha
        
        # Adiciona a última questão processada
        if q_atual and q_atual['certa'] and len(q_atual['erradas']) > 0:
            questoes.append(q_atual)
        
        for i, q in enumerate(questoes):
            certa = q['certa'] if q['certa'] else "Alternativa correta"
            erradas = q['erradas']
            while len(erradas) < 3: erradas.append("Alternativa incorreta genérica")
            
            opcoes = [
                (certa, '#166534', '#22c55e'),
                (erradas[0], '#991b1b', '#ef4444'),
                (erradas[1], '#991b1b', '#ef4444'),
                (erradas[2], '#991b1b', '#ef4444')
            ]
            random.shuffle(opcoes)
            
            letras = ["A)", "B)", "C)", "D)"]
            botoes_html = ""
            for idx, op in enumerate(opcoes):
                texto_op, bg_cor, borda_cor = op
                texto_op = texto_op.replace('*', '').replace('"', '')
                botoes_html += f'\n        <button onclick="this.style.background=\'{bg_cor}\'; this.style.borderColor=\'{borda_cor}\'">{letras[idx]} {texto_op}</button>'
            
            pergunta_formatada = f"{i+1}. {q['pergunta']}" if q['pergunta'] else f"{i+1}. Pergunta gerada"
            cards_html += f'\n    <div class="card">\n        <div class="pergunta">{pergunta_formatada}</div>{botoes_html}\n    </div>'
        
        quiz_final = template_html.replace("{cards_gerados}", cards_html)
        with open(os.path.join(pasta_docs, "Quiz-Fixacao.html"), "w", encoding="utf-8") as f:
            f.write(quiz_final)
        print("    [OK] Quiz-Fixacao.html salvo em 6_Documentos.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        processar_aula(sys.argv[1])
