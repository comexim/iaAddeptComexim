"""
Verificação contas a pagar: hoje, semana, abril 2026
"""
import sys
from decimal import Decimal
from datetime import datetime, timedelta
import pytz
sys.path.insert(0, '/opt/agente-comexim-whatsapp')
from app.core.database import sql_client

TZ = pytz.timezone("America/Sao_Paulo")
hoje = datetime.now(TZ)

def fmt(d): return d.strftime("%Y%m%d")
def total_dedup(records):
    vistos = set()
    total = 0
    qtd = 0
    for r in records:
        num = str(r.get('numero','')).strip()
        parc = str(r.get('parcela','')).strip()
        fil = str(r.get('filial','')).strip()
        forn = str(r.get('fornecedor','')).strip()
        v = float(r.get('valor', 0) or 0)
        nat = str(r.get('natureza','')).strip()
        chave = f"{num}_{parc}_{fil}_{forn}_{v}_{nat}"
        if chave in vistos: continue
        vistos.add(chave)
        total += v
        qtd += 1
    return qtd, total

# 1. Hoje
data_hoje = fmt(hoje)
r = sql_client.execute_function("IA_ContasAPagarPar", {"data_inicio": data_hoje, "data_fim": data_hoje})
qtd, tot = total_dedup(r)
print(f"=== HOJE ({data_hoje}) ===")
print(f"Títulos: {qtd} | Total: R$ {tot:,.2f}")
print(f"IA disse: R$ 80.738,84")
print(f"Bate? {'SIM ✓' if abs(tot - 80738.84) < 1 else f'NÃO ✗ (dif: R$ {abs(tot-80738.84):,.2f})'}")

# 2. Semana (seg a dom desta semana)
dia_semana = hoje.weekday()  # 0=seg
inicio_semana = hoje - timedelta(days=dia_semana)
fim_semana = inicio_semana + timedelta(days=6)
r = sql_client.execute_function("IA_ContasAPagarPar", {"data_inicio": fmt(inicio_semana), "data_fim": fmt(fim_semana)})
qtd, tot = total_dedup(r)
print(f"\n=== SEMANA ({fmt(inicio_semana)} a {fmt(fim_semana)}) ===")
print(f"Títulos: {qtd} | Total: R$ {tot:,.2f}")
print(f"IA disse: R$ 39.833.651,38")
print(f"Bate? {'SIM ✓' if abs(tot - 39833651.38) < 1 else f'NÃO ✗ (dif: R$ {abs(tot-39833651.38):,.2f})'}")

# 3. Abril 2026
r = sql_client.execute_function("IA_ContasAPagarPar", {"data_inicio": "20260401", "data_fim": "20260430"})
qtd, tot = total_dedup(r)
print(f"\n=== ABRIL 2026 ===")
print(f"Títulos: {qtd} | Total: R$ {tot:,.2f}")
print(f"IA disse: Não há contas")
print(f"Bate? {'SIM ✓ (banco também vazio)' if qtd == 0 else f'NÃO ✗ — banco tem {qtd} títulos, R$ {tot:,.2f}'}")
