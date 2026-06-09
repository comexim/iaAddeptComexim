"""
Valida: Quantos contratos embarcaram na última semana?
Resposta IA: 7 contratos, R$ 1.097.727,24
"""
import pyodbc
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASSWORD')}"
)

print("="*80)
print("VALIDACAO: Quantos contratos embarcaram na ultima semana?")
print("="*80)
print()

print("Resposta da IA: 7 contratos, R$ 1.097.727,24")
print()

# Calcular última semana (hoje = 2026-01-30, última semana = 2026-01-24 a 2026-01-30)
data_hoje = "2026-01-30"
data_inicio = "2026-01-24"

print(f"Periodo: {data_inicio} ate {data_hoje} (7 dias)")
print()

print("Consultando SQL Server...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Query com filtro de período específico
query = f"""
SELECT *
FROM dbo.IA_Vendas()
WHERE emissao >= '{data_inicio.replace('-', '')}'
  AND emissao <= '{data_hoje.replace('-', '')}'
"""

print(f"Query: {query}")
print()

cursor.execute(query)
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]
cursor.close()
conn.close()

print(f"Total de registros no periodo: {len(results)}")
print()

# Contar contratos únicos
contratos_unicos = set(r.get("numeroContrato") for r in results if r.get("numeroContrato"))
print(f"Contratos unicos: {len(contratos_unicos)}")

# Somar valor total
valor_total = sum(float(r.get("valorTotal", 0) or 0) for r in results)
print(f"Valor total: R$ {valor_total:,.2f}")
print()

# Mostrar contratos
print("Contratos encontrados:")
for contrato in sorted(contratos_unicos):
    contrato_data = [r for r in results if r.get("numeroContrato") == contrato]
    valor_contrato = sum(float(r.get("valorTotal", 0) or 0) for r in contrato_data)
    emissao = contrato_data[0].get("emissao") if contrato_data else "N/A"
    print(f"  - {contrato}: R$ {valor_contrato:,.2f} (emissao: {emissao})")
print()

# Comparar
ia_contratos = 7
ia_valor = 1097727.24
diferenca_contratos = abs(len(contratos_unicos) - ia_contratos)
diferenca_valor = abs(valor_total - ia_valor)

print("="*80)
print("COMPARACAO:")
print("="*80)
print(f"IA: {ia_contratos} contratos, R$ {ia_valor:,.2f}")
print(f"SQL: {len(contratos_unicos)} contratos, R$ {valor_total:,.2f}")
print(f"Diferenca: {diferenca_contratos} contratos, R$ {diferenca_valor:,.2f}")
print()

if diferenca_contratos == 0 and diferenca_valor < 0.01:
    print("✅ [OK] VALOR CORRETO!")
else:
    print(f"❌ [ERRO] Diferenca de {diferenca_contratos} contratos e R$ {diferenca_valor:,.2f}")

print("="*80)
