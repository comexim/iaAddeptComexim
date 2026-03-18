"""
Verificação de respostas de vendas
"""
import sys
from decimal import Decimal
sys.path.insert(0, '/opt/agente-comexim-whatsapp')
from app.core.database import sql_client

def consultar(inicio, fim, label):
    results = sql_client.execute_function("IA_VendasPar", {"data_inicio": inicio, "data_fim": fim})
    contratos = set()
    sacas = 0
    valor = 0
    for row in results:
        c = str(row.get('contrato', '')).strip()
        f = str(row.get('filial', '')).strip()
        if c:
            contratos.add(f"{c}_{f}" if f else c)
        s = row.get('sacas', 0) or 0
        v = row.get('valorTotal', 0) or 0
        if isinstance(s, Decimal): s = float(s)
        if isinstance(v, Decimal): v = float(v)
        sacas += s
        valor += v
    # Remove duplicatas de sacas/valor (mesmo contrato aparece múltiplas vezes)
    # Usa primeiro registro de cada contrato
    vistos = set()
    sacas2 = 0
    valor2 = 0
    for row in results:
        c = str(row.get('contrato', '')).strip()
        f = str(row.get('filial', '')).strip()
        chave = f"{c}_{f}" if f else c
        if chave in vistos or not c:
            continue
        vistos.add(chave)
        s = row.get('sacas', 0) or 0
        v = row.get('valorTotal', 0) or 0
        if isinstance(s, Decimal): s = float(s)
        if isinstance(v, Decimal): v = float(v)
        sacas2 += s
        valor2 += v
    print(f"\n=== {label} ===")
    print(f"Contratos únicos: {len(contratos)}")
    print(f"Total sacas (dedup): {sacas2:,.2f}")
    print(f"Valor total (dedup): R$ {valor2:,.2f}")

# 1. Março 2026 - sacas
consultar("2026/03", "2026/03", "Março 2026")
print("IA disse: 77.741,69 sacas")

# 2. Fevereiro 2026 - valor
consultar("2026/02", "2026/02", "Fevereiro 2026")
print("IA disse: R$ 37.168.978,56")

# 3. NESTRADE em março 2026
print("\n=== NESTRADE - Março 2026 ===")
results = sql_client.execute_function("IA_VendasPar", {"data_inicio": "2026/03", "data_fim": "2026/03"})
nestrade = [r for r in results if 'NESTRADE' in str(r.get('cliente', '')).upper()]
vistos = set()
for row in nestrade:
    c = str(row.get('contrato', '')).strip()
    if c in vistos: continue
    vistos.add(c)
    s = row.get('sacas', 0) or 0
    v = row.get('valorTotal', 0) or 0
    if isinstance(s, Decimal): s = float(s)
    if isinstance(v, Decimal): v = float(v)
    print(f"  {c}: {s:,.2f} sacas | R$ {v:,.2f}")
print(f"Total contratos NESTRADE: {len(vistos)}")
print("IA disse: 570/25A, 532/25E, 379/25H, 045/26 (4 contratos)")
