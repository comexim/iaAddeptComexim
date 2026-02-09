#!/bin/bash
cd /opt/agente-comexim-whatsapp && ./venv/bin/python << 'EOF'
import pyodbc
conn_str = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=200.221.173.187,6776;DATABASE=Protheus;UID=iaSelect;PWD=User_CMX#6776_Sql@;TrustServerCertificate=yes;"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT * FROM dbo.IA_Vendas() WHERE mesEmbarque = '2026/02'")
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]
cursor.close()
conn.close()

print("="*80)
print("VERIFICACAO: Contratos com embarque em fevereiro 2026")
print("="*80)
print(f"Total de registros encontrados: {len(results)}")
print()

if len(results) > 0:
    # Mostra primeiros 20
    print("Primeiros 20 contratos:")
    for i, r in enumerate(results[:20], 1):
        print(f"  {i}. Contrato: {r.get('contrato')}, Cliente: {r.get('cliente')}, Sacas: {r.get('sacas')}")

    print()

    # Mostra contratos únicos
    contratos_unicos = set(r.get('contrato') for r in results if r.get('contrato'))
    print(f"Total de contratos únicos: {len(contratos_unicos)}")

    # Soma total
    total_sacas = sum(float(r.get('sacas', 0) or 0) for r in results)
    total_valor = sum(float(r.get('valorTotal', 0) or 0) for r in results)
    print(f"Total de sacas: {total_sacas:,.2f}")
    print(f"Valor total: R$ {total_valor:,.2f}")
else:
    print("NENHUM contrato encontrado com mesEmbarque = '2026/02'")

print("="*80)
EOF
