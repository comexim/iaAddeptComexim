"""
Debug: Por que o filtro de "exportação" não está funcionando?
"""

query_original = "Quantas sacas para exportação?"
query_lower = query_original.lower()

print(f"Query original: {query_original}")
print(f"Query lower: {query_lower}")
print()

# Testar padrões
padroes = ["para exportação", "para exportacao", "exportação", "exportacao", "sacas de exportação"]

print("Testando padrões:")
for padrao in padroes:
    if padrao in query_lower:
        print(f"  [OK] Padrão '{padrao}' ENCONTRADO")
    else:
        print(f"  [X] Padrão '{padrao}' NÃO encontrado")

print()
print("Análise:")
print(f"  'exportação' in query_lower: {'exportação' in query_lower}")
print(f"  'exportacao' in query_lower: {'exportacao' in query_lower}")
print(f"  repr(query_lower): {repr(query_lower)}")
