"""
Testa o FIX para query comparativa: "Temos mais café para exportação ou consumo?"
Deve NÃO aplicar filtro automático e retornar valores corretos
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import pesquisa_estoque
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("TESTE DO FIX: Query comparativa (exportação vs consumo)")
print("=" * 80)
print()

query = "Temos mais café para exportação ou consumo?"
print(f"Query: '{query}'")
print()

print("Chamando pesquisa_estoque()...")
print()

resultado = pesquisa_estoque(query)

print("=" * 80)
print("RESULTADO RETORNADO PELA FUNÇÃO:")
print("=" * 80)
print(resultado)
print()

print("=" * 80)
print("ANÁLISE:")
print("=" * 80)

# Verificar se a função detectou como comparativa
if "Query comparativa detectada" in resultado or "comparativa" in resultado.lower():
    print("[OK] Função detectou que é uma query comparativa")
else:
    print("[INFO] Verificar nos logs se detectou comparativa")

# Verificar valores esperados
if "113.113,10" in resultado or "113113.10" in resultado or "113,113" in resultado:
    print("[OK] Valor de exportação presente (113.113,10)")
else:
    print("[?] Verificar valor de exportação")

if "22.015,81" in resultado or "22015.81" in resultado or "22,015" in resultado:
    print("[OK] Valor de consumo CORRETO presente (22.015,81)")
elif "11.022,11" in resultado or "11022.11" in resultado or "11,022" in resultado:
    print("[ERRO] Valor de consumo INCORRETO (11.022,11) - FIX NÃO FUNCIONOU!")
else:
    print("[?] Verificar valor de consumo")

print()
print("=" * 80)
print("VALORES ESPERADOS:")
print("=" * 80)
print("Exportação: 113.113,10 sacas")
print("Consumo: 22.015,81 sacas")
print("Total geral: 135.131,22 sacas (931 registros)")
print()
print("Se o consumo vier como 11.022,11 → filtro foi aplicado incorretamente")
print("Se o consumo vier como 22.015,81 → FIX está funcionando!")
print("=" * 80)
