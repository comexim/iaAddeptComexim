#!/usr/bin/env python3
"""
Verificar contratos com embarque em fevereiro 2026
"""
import sys
sys.path.insert(0, '/opt/agente-comexim-whatsapp')

from app.core.database import SQLServerClient

print("="*80)
print("VERIFICACAO: Contratos com embarque em fevereiro 2026")
print("="*80)

client = SQLServerClient()

# Busca contratos com mesEmbarque = 2026/02
print("\n[1] Buscando contratos com mesEmbarque = '2026/02'...")
results = client.execute_function("IA_Vendas", filters={"mesEmbarque": "2026/02"})

print(f"Total encontrados: {len(results)}")

if len(results) > 0:
    print("\nPrimeiros 20 contratos:")
    for i, r in enumerate(results[:20], 1):
        print(f"  {i}. Contrato: {r.get('contrato')}, Cliente: {r.get('cliente')}, Sacas: {r.get('sacas')}, mesEmbarque: {r.get('mesEmbarque')}")

    # Mostra contratos únicos
    contratos_unicos = set(r.get('contrato') for r in results if r.get('contrato'))
    print(f"\nTotal de contratos únicos: {len(contratos_unicos)}")

    # Soma total de sacas
    total_sacas = sum(float(r.get('sacas', 0) or 0) for r in results)
    print(f"Total de sacas: {total_sacas:,.2f}")

    # Soma valor total
    total_valor = sum(float(r.get('valorTotal', 0) or 0) for r in results)
    print(f"Valor total: R$ {total_valor:,.2f}")
else:
    print("\n❌ NENHUM contrato encontrado com mesEmbarque = '2026/02'")
    print("\nVerificando outros formatos...")

    # Tenta outros formatos
    all_results = client.execute_function("IA_Vendas", filters=None)
    fev_variants = [r for r in all_results if '02' in str(r.get('mesEmbarque', '')) and '2026' in str(r.get('mesEmbarque', ''))]

    print(f"\nContratos com '02' e '2026' no mesEmbarque: {len(fev_variants)}")
    if fev_variants:
        for r in fev_variants[:5]:
            print(f"  - mesEmbarque: '{r.get('mesEmbarque')}', contrato: {r.get('contrato')}")

print("\n" + "="*80)
