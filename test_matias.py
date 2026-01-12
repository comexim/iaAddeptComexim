"""
Teste local da extração de cliente: MATIAS RUIZ & CIA SA
"""
import re

query = "quantos contratos de venda de embarque temos para o cliente MATIAS RUIZ & CIA SA para este mês 2025?"
query_lower = query.lower().strip()

patterns = [
    # Cliente explícito: "para o cliente NOME"
    r'(?:para|do|da)\s+(?:o\s+|a\s+)?cliente\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+temos|\s+tem|\s+para|\s+no|\s+em|\s+na|\s+do|\s+da|\?)',
    # Cliente implícito: "para a starbucks"
    r'para\s+(?:a\s+|o\s+)([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+temos|\s+tem|\s+para|\s+no|\s+em)',
    r'da\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+em|\s+no|\s+para)',
    r'do\s+([a-záàâãéèêíïóôõöúçñ\s&\.]+?)(?:\s+em|\s+no|\s+para)',
]

print(f"Query original: {query}")
print(f"Query lowercase: {query_lower}\n")

for i, pattern in enumerate(patterns, 1):
    match = re.search(pattern, query_lower)
    if match:
        client_name = match.group(1).strip()
        print(f"[OK] Pattern {i} MATCHED!")
        print(f"   Regex: {pattern}")
        print(f"   Cliente extraido: '{client_name}'")
        break
    else:
        print(f"[X] Pattern {i} nao match")

if not match:
    print("\n[ERRO] NENHUM pattern encontrou o cliente!")
