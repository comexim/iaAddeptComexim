"""
Verifica EXATAMENTE como está o nome MATIAS RUIZ no banco
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

# Busca registros de dezembro 2025
results = sql_client.execute_function("IA_Vendas", {"emissao": "20251201"})

print(f"Total de registros em dezembro 2025: {len(results)}\n")

# Busca por MATIAS (case insensitive)
matias_records = []
for row in results:
    cliente = str(row.get("cliente", ""))
    if "MATIAS" in cliente.upper():
        matias_records.append(row)
        print(f"ENCONTRADO: '{cliente}' - Contrato: {row.get('numero', 'N/A')}")

print(f"\n\nTotal registros com MATIAS: {len(matias_records)}")

if len(matias_records) == 0:
    print("\n\nNENHUM REGISTRO COM 'MATIAS' ENCONTRADO!")
    print("\nMostrando TODOS os 73 clientes:\n")
    clientes_unicos = set()
    for row in results:
        cliente = str(row.get("cliente", "")).strip()
        clientes_unicos.add(cliente)

    for cliente in sorted(clientes_unicos):
        print(f"  - '{cliente}'")

sql_client.close()
