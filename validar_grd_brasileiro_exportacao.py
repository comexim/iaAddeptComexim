"""
Valida: Quanto café GRD brasileiro temos para exportação?
Resposta IA: 33.168,26 sacas
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
print("VALIDACAO: Quanto cafe GRD brasileiro temos para exportacao?")
print("="*80)
print()

print("Resposta da IA: 33.168,26 sacas")
print()

print("Consultando SQL Server...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT * FROM dbo.IA_Estoque()")
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]
cursor.close()
conn.close()

print(f"Total de registros: {len(results)}")
print()

# Filtrar: linha=GRD, pais=BRASIL, sacasExportacao > 0
grd_brasil = [r for r in results if r.get("linha") == "GRD" and str(r.get("pais", "")).upper() == "BRASIL"]
print(f"Registros GRD brasileiro: {len(grd_brasil)}")

total_exportacao = sum(float(r.get("sacasExportacao", 0) or 0) for r in grd_brasil)
print(f"Total sacasExportacao: {total_exportacao:,.2f} sacas")
print()

# Comparar
ia_valor = 33168.26
diferenca = abs(total_exportacao - ia_valor)

print("="*80)
print("COMPARACAO:")
print("="*80)
print(f"IA: {ia_valor:,.2f} sacas")
print(f"SQL: {total_exportacao:,.2f} sacas")
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

if diferenca < 0.01:
    print("✅ [OK] VALOR CORRETO!")
else:
    print(f"❌ [ERRO] Diferenca de {diferenca:,.2f} sacas")

print("="*80)
