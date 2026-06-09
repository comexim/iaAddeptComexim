"""
Verificação de estoque contra o que a IA respondeu
- Total: 109.464,36 sacas (14.796,58 consumo + 94.666,24 exportação)
- PVA: 8.839,98 sacas (8.837,85 consumo + 2,11 exportação)
"""
import sys
from decimal import Decimal
sys.path.insert(0, '/opt/agente-comexim-whatsapp')
from app.core.database import sql_client

def float_val(v):
    if isinstance(v, Decimal): return float(v)
    return float(v or 0)

print("Consultando IA_Estoque()...")
results = sql_client.execute_function("IA_Estoque", {})
print(f"Registros brutos: {len(results)}")

# Totais gerais
total_sacas = sum(float_val(r.get('sacas', 0)) for r in results)
total_consumo = sum(float_val(r.get('sacasConsumo', 0)) for r in results)
total_exportacao = sum(float_val(r.get('sacasExportacao', 0)) for r in results)

print(f"\n=== TOTAL GERAL ===")
print(f"Total sacas:     {total_sacas:,.2f}")
print(f"  Consumo:       {total_consumo:,.2f}")
print(f"  Exportação:    {total_exportacao:,.2f}")
print(f"IA disse: 109.464,36 sacas (14.796,58 consumo + 94.666,24 exportação)")
print(f"Total bate? {'SIM ✓' if abs(total_sacas - 109464.36) < 1 else f'NÃO ✗ (dif: {abs(total_sacas-109464.36):,.2f})'}")
print(f"Consumo bate? {'SIM ✓' if abs(total_consumo - 14796.58) < 1 else f'NÃO ✗ (dif: {abs(total_consumo-14796.58):,.2f})'}")
print(f"Exportação bate? {'SIM ✓' if abs(total_exportacao - 94666.24) < 1 else f'NÃO ✗ (dif: {abs(total_exportacao-94666.24):,.2f})'}")

# Por linha
from collections import defaultdict
por_linha = defaultdict(lambda: {"sacas": 0, "consumo": 0, "exportacao": 0})
for r in results:
    linha = str(r.get('linha', '') or '').strip() or 'SEM LINHA'
    por_linha[linha]["sacas"] += float_val(r.get('sacas', 0))
    por_linha[linha]["consumo"] += float_val(r.get('sacasConsumo', 0))
    por_linha[linha]["exportacao"] += float_val(r.get('sacasExportacao', 0))

print(f"\n=== POR LINHA ===")
for linha, v in sorted(por_linha.items(), key=lambda x: -x[1]["sacas"]):
    print(f"  {linha}: {v['sacas']:,.2f} sacas (consumo: {v['consumo']:,.2f} | export: {v['exportacao']:,.2f})")

# Filtro PVA
pva = por_linha.get('PVA', {"sacas": 0, "consumo": 0, "exportacao": 0})
print(f"\n=== PVA ESPECÍFICO ===")
print(f"Total PVA:    {pva['sacas']:,.2f}")
print(f"  Consumo:    {pva['consumo']:,.2f}")
print(f"  Exportação: {pva['exportacao']:,.2f}")
print(f"IA disse: 8.839,98 sacas (8.837,85 consumo + 2,11 exportação)")
print(f"Total bate? {'SIM ✓' if abs(pva['sacas'] - 8839.98) < 1 else f'NÃO ✗ (dif: {abs(pva[\"sacas\"]-8839.98):,.2f})'}")
print(f"Consumo bate? {'SIM ✓' if abs(pva['consumo'] - 8837.85) < 1 else f'NÃO ✗ (dif: {abs(pva[\"consumo\"]-8837.85):,.2f})'}")
print(f"Exportação bate? {'SIM ✓' if abs(pva['exportacao'] - 2.11) < 0.1 else f'NÃO ✗ (dif: {abs(pva[\"exportacao\"]-2.11):,.2f})'}")
