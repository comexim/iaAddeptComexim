"""
Verificar se contrato 031/25 existe no banco
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
print("BUSCA: Contrato 031/25 ou 31/25")
print("="*80)
print()

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Busca ampla - qualquer contrato que contenha "31/25"
query = """
SELECT contrato, mesEmbarque, cliente, sacas, diferencial, valorFixado, valorTotal
FROM dbo.IA_Vendas()
WHERE contrato LIKE '%31/25%'
"""

print("Query 1: Contratos contendo '31/25'")
print(query)
cursor.execute(query)
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]

print(f"\nResultados: {len(results)}")
for row in results:
    row_dict = dict(zip(columns, row))
    print(f"  - {row_dict}")

print()
print("="*80)

# Busca por mesEmbarque janeiro 2026
query2 = """
SELECT contrato, mesEmbarque, cliente, sacas, diferencial, valorFixado, valorTotal
FROM dbo.IA_Vendas()
WHERE mesEmbarque = '2026/01'
AND contrato LIKE '%31%'
"""

print("\nQuery 2: Contratos com '31' em janeiro 2026")
print(query2)
cursor.execute(query2)
results2 = cursor.fetchall()

print(f"\nResultados: {len(results2)}")
for row in results2:
    row_dict = dict(zip(columns, row))
    print(f"  - {row_dict}")

print()
print("="*80)

# Lista todos os contratos únicos de janeiro 2026 que terminam com /25
query3 = """
SELECT DISTINCT contrato
FROM dbo.IA_Vendas()
WHERE mesEmbarque = '2026/01'
AND contrato LIKE '%/25%'
ORDER BY contrato
"""

print("\nQuery 3: Todos os contratos /25 com embarque em janeiro 2026")
cursor.execute(query3)
results3 = cursor.fetchall()

print(f"\nTotal de contratos /25 em jan/2026: {len(results3)}")
for row in results3:
    print(f"  - {row[0]}")

cursor.close()
conn.close()
