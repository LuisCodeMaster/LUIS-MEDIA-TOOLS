import sys
import os
import re
import ollama

def gerar_slides_ia(prompt_usuario, output_path="slides/roteiro-aula.md"):
    system_instruction = """
Voce e um professor e designer instrucional especialista.
Crie uma apresentacao didatica em Markdown baseada no tema pedido.

REGRAS ESTRITAS DE FORMATO:
1. Separe cada slide EXCLUSIVAMENTE com uma linha contendo: ---
2. O primeiro slide DEVE ter esta estrutura:
   # Titulo da Aula
   ### Subtitulo
   **Professor**
3. Para dividir conteudos em colunas paralelas:
   || COLUNA
   topicos coluna 1
   || COLUNA
   topicos coluna 2
   || FIM
4. Use caixas de destaque quando util:
   [DICA] Texto da dica
   [ATENCAO] Texto de aviso
5. Use notas para o apresentador em slides-chave:
   [NOTA] Observacao que nao aparece na tela principal
6. Blocos de codigo devem usar sintaxe padrao: ```linguagem ... ```
7. Escreva em Portugues. NAO inclua explicacoes antes ou depois, responda APENAS com o conteudo Markdown.
"""

    print(f"[*] Gerando slides com Llama local para: '{prompt_usuario}'...")
    
    try:
        response = ollama.chat(
            model='llama3.2',
            messages=[
                {'role': 'system', 'content': system_instruction},
                {'role': 'user', 'content': f"Crie entre 5 e 7 slides didaticos sobre o tema: {prompt_usuario}"}
            ]
        )
        conteudo = response['message']['content'].strip()

        # Remove eventuais blocos de codigo externos que o modelo possa colocar
        if conteudo.startswith("```markdown"):
            conteudo = conteudo[11:]
        elif conteudo.startswith("```"):
            conteudo = conteudo[3:]
        if conteudo.endswith("```"):
            conteudo = conteudo[:-3]
        conteudo = conteudo.strip()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(conteudo)

        print(f"[OK] Roteiro gerado e salvo em: {output_path}")
    except Exception as e:
        print(f"[ERRO] Falha ao comunicar com Ollama: {e}")
        print("Certifique-se de que o servico do Ollama esta aberto.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tema = " ".join(sys.argv[1:])
    else:
        tema = input("Digite o tema para gerar os slides: ")
    gerar_slides_ia(tema)