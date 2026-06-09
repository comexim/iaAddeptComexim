"""
Debug: Por que não encontrou PVA?
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv

load_dotenv()

print("Buscando registros...")
results = sql_client.execute_function("dbo.IA_Estoque", None)

# Analisa primeiros 10 registros que tenham "pva" no nome
pva_encontrados = []

for r in results:
    linha = r.get("linha", "")
    linha_str = str(linha)

    if "pva" in linha_str.lower() or "PVA" in linha_str:
        pva_encontrados.append({
            "linha": linha,
            "linha_type": type(linha).__name__,
            "linha_repr": repr(linha),
            "linha_upper": linha_str.upper(),
            "sacas": r.get("sacas", 0)
        })

        if len(pva_encontrados) >= 5:
            break

print(f"\nEncontrados {len(pva_encontrados)} registros com 'PVA':")
print()

for i, item in enumerate(pva_encontrados, 1):
    print(f"Registro {i}:")
    print(f"  linha: {item['linha']}")
    print(f"  tipo: {item['linha_type']}")
    print(f"  repr: {item['linha_repr']}")
    print(f"  upper: {item['linha_upper']}")
    print(f"  sacas: {item['sacas']}")
    print()

# Teste do filtro
print("Teste de filtros:")
for item in pva_encontrados[:3]:
    linha_str = str(item['linha'])
    print(f"  linha='{item['linha']}'")
    print(f"    str(linha).upper() == 'PVA': {linha_str.upper() == 'PVA'}")
    print(f"    'PVA' in str(linha).upper(): {'PVA' in linha_str.upper()}")
    print(f"    str(linha).upper().strip() == 'PVA': {linha_str.upper().strip() == 'PVA'}")
    print()
