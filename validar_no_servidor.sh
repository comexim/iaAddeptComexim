#!/bin/bash
cd /opt/agente-comexim-whatsapp
python3 << 'PYTHON_EOF'
"""
Valida: Quantos contratos embarcaram na última semana?
Resposta IA: 7 contratos, R$ 1.097.727,24
"""
import pyodbc
import os
from dotenv import load_dotenv

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

data_inicio = "20260124"
data_fim = "20260130"

print(f"Periodo: {data_inicio} ate {data_fim} (7 dias)")
print()

print("Consultando SQL Server...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

query = f"SELECT * FROM dbo.IA_Vendas() WHERE emissao >= '{data_inicio}' AND emissao <= '{data_fim}'"
print(f"Query: {query}")
print()

cursor.execute(query)
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]
cursor.close()
conn.close()

print(f"Total de registros: {len(results)}")

# Contar contratos únicos
contratos_unicos = set(r.get("numeroContrato") for r in results if r.get("numeroContrato"))
print(f"Contratos unicos: {len(contratos_unicos)}")

# Somar valor total
valor_total = sum(float(r.get("valorTotal", 0) or 0) for r in results)
print(f"Valor total: R$ {valor_total:,.2f}")
print()

# Mostrar contratos
print("Contratos:")
for contrato in sorted(contratos_unicos):
    contrato_data = [r for r in results if r.get("numeroContrato") == contrato]
    valor = sum(float(r.get("valorTotal", 0) or 0) for r in contrato_data)
    emissao = contrato_data[0].get("emissao") if contrato_data else "N/A"
    print(f"  {contrato}: R$ {valor:,.2f} (emissao: {emissao})")
print()

# Comparar
ia_contratos = 7
ia_valor = 1097727.24
diff_contratos = abs(len(contratos_unicos) - ia_contratos)
diff_valor = abs(valor_total - ia_valor)

print("="*80)
print("COMPARACAO:")
print("="*80)
print(f"IA: {ia_contratos} contratos, R$ {ia_valor:,.2f}")
print(f"SQL: {len(contratos_unicos)} contratos, R$ {valor_total:,.2f}")
print(f"Diferenca: {diff_contratos} contratos, R$ {diff_valor:,.2f}")
print()

if diff_contratos == 0 and diff_valor < 0.01:
    print("✅ [OK] VALOR CORRETO!")
else:
    print(f"❌ [ERRO] Diferenca de {diff_contratos} contratos e R$ {diff_valor:,.2f}")

print("="*80)
PYTHON_EOF
