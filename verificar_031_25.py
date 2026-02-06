#!/usr/bin/env python3
"""
Verificar se contrato 031/25 existe no banco e listar contratos /25 com preço a fixar
Rodar no servidor: python3 verificar_031_25.py
"""
import sys
sys.path.insert(0, '/opt/agente-comexim-whatsapp')

from app.core.database import SQLServerClient

print("="*80)
print("VERIFICACAO: Contrato 031/25 e contratos /25 com preco a fixar")
print("="*80)

client = SQLServerClient()

# Query 1: Busca contrato 031/25 ou 31/25
print("\n[1] Buscando contratos que contenham '31/25'...")
results = client.execute_function("IA_Vendas", filters=None)
contratos_31_25 = [r for r in results if "31/25" in str(r.get("contrato", ""))]

print(f"Encontrados: {len(contratos_31_25)}")
for r in contratos_31_25:
    print(f"  - Contrato: {r.get('contrato')}, mesEmbarque: {r.get('mesEmbarque')}, cliente: {r.get('cliente')}, diferencial: {r.get('diferencial')}")

# Query 2: Busca contratos /25 com embarque em janeiro 2026
print("\n[2] Contratos /25 com mesEmbarque = '2026/01'...")
results_jan = client.execute_function("IA_Vendas", filters={"mesEmbarque": "2026/01"})
contratos_25_jan = [r for r in results_jan if "/25" in str(r.get("contrato", ""))]

print(f"Encontrados: {len(contratos_25_jan)}")
for r in contratos_25_jan[:20]:  # Limita a 20
    print(f"  - Contrato: {r.get('contrato')}, cliente: {r.get('cliente')}, valorFixado: {r.get('valorFixado')}, diferencial: {r.get('diferencial')}")

# Query 3: Busca contratos /25 com preco a fixar (valorFixado = 0 ou null)
print("\n[3] Contratos /25 com preco a fixar (valorFixado = 0 ou null) em janeiro 2026...")
preco_fixar = [r for r in contratos_25_jan if r.get("valorFixado") is None or r.get("valorFixado") == 0 or r.get("valorFixado") == 0.0]

print(f"Encontrados: {len(preco_fixar)}")
for r in preco_fixar:
    print(f"  - Contrato: {r.get('contrato')}, cliente: {r.get('cliente')}, valorFixado: {r.get('valorFixado')}, diferencial: {r.get('diferencial')}")

# Query 4: Todos os contratos com preco a fixar em janeiro 2026 (qualquer sufixo)
print("\n[4] TODOS os contratos com preco a fixar em janeiro 2026...")
todos_preco_fixar = [r for r in results_jan if r.get("valorFixado") is None or r.get("valorFixado") == 0 or r.get("valorFixado") == 0.0]

print(f"Total encontrados: {len(todos_preco_fixar)}")
contratos_unicos = set()
for r in todos_preco_fixar:
    contrato = r.get('contrato', '')
    if contrato not in contratos_unicos:
        contratos_unicos.add(contrato)
        print(f"  - Contrato: {contrato}, cliente: {r.get('cliente')}, valorFixado: {r.get('valorFixado')}")

print("\n" + "="*80)
print(f"RESUMO:")
print(f"  - Contratos contendo '31/25': {len(contratos_31_25)}")
print(f"  - Contratos /25 em jan/2026: {len(contratos_25_jan)}")
print(f"  - Contratos /25 com preco a fixar em jan/2026: {len(preco_fixar)}")
print(f"  - Total contratos com preco a fixar em jan/2026: {len(todos_preco_fixar)}")
print("="*80)
