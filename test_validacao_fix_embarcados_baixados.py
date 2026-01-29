"""
Validação: Contratos dezembro 2025 embarcados sem baixa
APÓS o deploy do fix 4379b0b
"""
import pyodbc
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# Conectar ao SQL Server
try:
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
        f"DATABASE={os.getenv('SQL_SERVER_DATABASE')};"
        f"UID={os.getenv('SQL_SERVER_USER')};"
        f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
        f"TrustServerCertificate=yes;"
        f"Connection Timeout=30;"
    )
except:
    # Tentar com driver alternativo
    conn = pyodbc.connect(
        f"DRIVER={{{os.getenv('SQL_SERVER_DRIVER')}}};"
        f"SERVER={os.getenv('SQL_SERVER_HOST')},{os.getenv('SQL_SERVER_PORT')};"
        f"DATABASE={os.getenv('SQL_SERVER_DATABASE')};"
        f"UID={os.getenv('SQL_SERVER_USER')};"
        f"PWD={os.getenv('SQL_SERVER_PASSWORD')};"
    )

cursor = conn.cursor()

print("=" * 80)
print("VALIDAÇÃO: Contratos dezembro 2025 embarcados sem baixa")
print("=" * 80)
print()

# Query para pegar contratos de dezembro 2025 embarcados mas não baixados
query = """
SELECT
    numeroContrato,
    nomeCliente,
    mesEmbarque,
    contratos_baixados_nov2025,
    contratos_baixados_dez2025,
    contratos_baixados_jan2026
FROM IA_Vendas(NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
WHERE mesEmbarque = '2025/12'
"""

cursor.execute(query)
rows = cursor.fetchall()

print(f"✅ Total de contratos embarcados em dezembro 2025: {len(rows)}")
print()

# Filtrar apenas os que NÃO foram baixados
nao_baixados = []
for row in rows:
    numero = row.numeroContrato
    cliente = row.nomeCliente
    mes_embarque = row.mesEmbarque
    baixados_nov = row.contratos_baixados_nov2025
    baixados_dez = row.contratos_baixados_dez2025
    baixados_jan = row.contratos_baixados_jan2026

    # Verificar se foi baixado em algum mês
    foi_baixado = False

    # Novembro 2025
    if baixados_nov and numero in baixados_nov:
        foi_baixado = True

    # Dezembro 2025
    if baixados_dez and numero in baixados_dez:
        foi_baixado = True

    # Janeiro 2026
    if baixados_jan and numero in baixados_jan:
        foi_baixado = True

    if not foi_baixado:
        nao_baixados.append({
            'numero': numero,
            'cliente': cliente,
            'mes_embarque': mes_embarque
        })

print(f"📊 Contratos embarcados em dezembro 2025 que NÃO foram baixados: {len(nao_baixados)}")
print()

print("=" * 80)
print("5 PRIMEIROS CONTRATOS (ordenados por número):")
print("=" * 80)
nao_baixados_sorted = sorted(nao_baixados, key=lambda x: x['numero'])
for i, contrato in enumerate(nao_baixados_sorted[:5], 1):
    print(f"{i}. {contrato['numero']} - {contrato['cliente']}")

print()
print("=" * 80)
print("COMPARAÇÃO COM RESPOSTA DA IA:")
print("=" * 80)
print()
print("IA disse: 9 contratos")
print(f"Real: {len(nao_baixados)} contratos")
print()
print("IA listou:")
print("1. 564/25A (THE FOLGER COFFEE)")
print("2. 564/25B (THE FOLGER COFFEE)")
print("3. 030/25 (AHOLD COFFEE)")
print("4. 033/25 (AHOLD COFFEE)")
print("5. 037/25 (AHOLD COFFEE)")
print()
print("Deveria listar:")
for i, contrato in enumerate(nao_baixados_sorted[:5], 1):
    print(f"{i}. {contrato['numero']} ({contrato['cliente']})")

print()
print("=" * 80)
print("VERIFICAÇÃO:")
print("=" * 80)

# Verificar se os contratos listados pela IA estão na lista real
contratos_ia = ['564/25A', '564/25B', '030/25', '033/25', '037/25']
numeros_reais = [c['numero'] for c in nao_baixados]

print()
print("Os contratos listados pela IA estão corretos?")
for contrato_ia in contratos_ia:
    if contrato_ia in numeros_reais:
        print(f"  ✅ {contrato_ia} - ESTÁ na lista real")
    else:
        print(f"  ❌ {contrato_ia} - NÃO ESTÁ na lista real")

print()
if len(nao_baixados) == 9:
    print("✅ QUANTIDADE CORRETA: 9 contratos")
else:
    print(f"❌ QUANTIDADE ERRADA: IA disse 9, mas são {len(nao_baixados)}")

# Listar TODOS os contratos para análise
print()
print("=" * 80)
print(f"TODOS OS {len(nao_baixados)} CONTRATOS (para análise):")
print("=" * 80)
for i, contrato in enumerate(nao_baixados_sorted, 1):
    print(f"{i:2}. {contrato['numero']:15} {contrato['cliente']}")

cursor.close()
conn.close()
