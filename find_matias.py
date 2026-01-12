"""
Busca MATIAS RUIZ em TODOS os períodos
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

# Busca TODOS os registros (sem filtro de data)
print("Buscando MATIAS RUIZ em TODOS os períodos...\n")
results = sql_client.execute_function("IA_Vendas", {})

# Busca por MATIAS
matias_records = []
for row in results:
    cliente = str(row.get("cliente", ""))
    if "MATIAS" in cliente.upper():
        matias_records.append(row)

print(f"Total registros com MATIAS: {len(matias_records)}\n")

if len(matias_records) > 0:
    print("Contratos MATIAS RUIZ encontrados:\n")
    for row in matias_records:
        cliente = row.get("cliente", "")
        numero = row.get("numero", "")
        emissao = row.get("emissao", "")
        # Converte emissao YYYYMMDD para DD/MM/YYYY
        if emissao and len(str(emissao)) == 8:
            emissao_str = str(emissao)
            emissao_formatada = f"{emissao_str[6:8]}/{emissao_str[4:6]}/{emissao_str[0:4]}"
        else:
            emissao_formatada = emissao

        print(f"  - Cliente: {cliente}")
        print(f"    Contrato: {numero}")
        print(f"    Data: {emissao_formatada}")
        print()
else:
    print("NENHUM registro com MATIAS encontrado em NENHUM período!")

sql_client.close()
