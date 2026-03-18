"""
Verificação direta: contas a pagar para amanhã (2026-03-19)
Compara com o que a IA retornou:
- 24 contas
- Total: R$ 5.586.129,60
- Décio Bruxel: R$ 2.583.408,75
- Coop. Agropecuária D: R$ 1.613.300,00
- Marcelo Martins do Canto: R$ 566.066,34
- Santo Antônio Café de Montanha: R$ 280.234,27
- Auto Posto Santa Fé Ltda: R$ 40.079,62
"""
import sys
import os
sys.path.insert(0, '/opt/agente-comexim-whatsapp')
os.chdir('/opt/agente-comexim-whatsapp')

from decimal import Decimal
from app.core.database import sql_client

# Amanhã = 2026-03-19
DATA = "20260319"

print(f"Consultando IA_ContasAPagarPar('{DATA}', '{DATA}')...")
result_list = sql_client.execute_function("dbo.IA_ContasAPagarPar", {"data_inicio": DATA, "data_fim": DATA})
print(f"Total bruto retornado: {len(result_list)} registros")

# Deduplicação igual ao código
titulos_vistos = set()
result_dedup = []
for r in result_list:
    fornecedor = str(r.get('fornecedor', '')).strip()
    valor = float(r.get('valor', 0) or 0)
    natureza = str(r.get('natureza', '')).strip()
    chave = f"{r.get('numero', '')}_{r.get('parcela', '')}_{r.get('filial', '')}_{fornecedor}_{valor}_{natureza}"
    if chave not in titulos_vistos:
        titulos_vistos.add(chave)
        result_dedup.append(r)

print(f"Após deduplicação: {len(result_dedup)} registros únicos")

# Total
total = 0
por_fornecedor = {}
for r in result_dedup:
    v = r.get('valor', 0)
    if isinstance(v, Decimal): v = float(v)
    elif not isinstance(v, (int, float)): v = 0
    total += v
    forn = str(r.get('fornecedor', '')).strip()
    por_fornecedor[forn] = por_fornecedor.get(forn, 0) + v

print(f"\nTotal geral: R$ {total:,.2f}")
print(f"\nTop 10 fornecedores:")
for forn, val in sorted(por_fornecedor.items(), key=lambda x: -x[1])[:10]:
    print(f"  {forn}: R$ {val:,.2f}")

print(f"\nIA disse: 24 contas, R$ 5.586.129,60")
print(f"BD retorna: {len(result_dedup)} contas, R$ {total:,.2f}")
print(f"Bate? {'SIM ✓' if abs(total - 5586129.60) < 1 else 'NÃO ✗ - diferença: R$ ' + f'{abs(total - 5586129.60):,.2f}'}")
