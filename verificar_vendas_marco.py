"""
Verifica contratos de março 2026 no banco
"""
import sys
sys.path.insert(0, '/opt/agente-comexim-whatsapp')

from app.core.database import sql_client

filters = {"data_inicio": "2026/03", "data_fim": "2026/03"}
print(f"Consultando IA_VendasPar(2026/03, 2026/03)...")
results = sql_client.execute_function("IA_VendasPar", filters)
print(f"Registros brutos: {len(results)}")

# Contratos únicos por número+filial
contratos_unicos = set()
for row in results:
    c = str(row.get('contrato', '')).strip()
    f = str(row.get('filial', '')).strip()
    if c:
        contratos_unicos.add(f"{c}_{f}" if f else c)

print(f"Contratos únicos (contrato+filial): {len(contratos_unicos)}")
print(f"\nIA disse: 102 contratos")
print(f"Bate? {'SIM ✓' if len(contratos_unicos) == 102 else f'NÃO ✗ — banco tem {len(contratos_unicos)}'}")
