#!/bin/bash
cd /opt/agente-comexim-whatsapp && ./venv/bin/python << 'EOF'
import pyodbc
conn_str = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=200.221.173.187,6776;DATABASE=Protheus;UID=iaSelect;PWD=User_CMX#6776_Sql@;TrustServerCertificate=yes;"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT * FROM dbo.IA_ContasAPagar() WHERE vencimento = '20260227'")
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]
cursor.close()
conn.close()

print("="*80)
print(f"CONTAS A PAGAR com vencimento = '20260227'")
print("="*80)
print(f"Total de registros: {len(results)}")
print()

total = 0
for i, r in enumerate(results, 1):
    valor = float(r.get('valor', 0) or 0)
    total += valor
    print(f"{i}. {r.get('fornecedor', 'N/A')[:30]:30} - R$ {valor:>12,.2f} - Natureza: {r.get('natureza', 'N/A')[:40]}")
    print(f"   Numero: {r.get('numero')}, Parcela: {r.get('parcela')}, Filial: {r.get('filial')}")

print()
print(f"TOTAL: R$ {total:,.2f}")
print("="*80)
EOF
