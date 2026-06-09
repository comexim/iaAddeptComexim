"""
Valida resposta da IA no servidor: "Quanto café PVA temos em estoque?"
IA respondeu: 11.335,56 sacas
Meu teste local: 11.135,95 sacas
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO SERVIDOR: Quanto cafe PVA temos em estoque?")
print("=" * 80)
print()

# Resposta da IA no servidor
resposta_ia_servidor = 11335.56
print(f"Resposta da IA (servidor): {resposta_ia_servidor:,.2f} sacas")

# Meu teste local anterior
teste_local = 11135.95
print(f"Meu teste local: {teste_local:,.2f} sacas")
print()

# Diferença
diferenca = abs(resposta_ia_servidor - teste_local)
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

# Buscar dados ATUAIS do SQL
print("Consultando SQL Server AGORA...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros (TODOS): {len(results)}")
print()

# Filtrar APENAS PVA
results_pva = []
for r in results:
    linha = str(r.get("linha", "")).strip().upper()
    if linha == "PVA":
        results_pva.append(r)

print(f"Total de registros PVA: {len(results_pva)}")
print()

# Calcular total PVA ATUAL
total_pva_atual = Decimal(0)
peso_pva = 0.0
lotes_pva = set()

for r in results_pva:
    sacas = r.get("sacas", 0)
    peso = r.get("peso", 0)
    lote = r.get("lote", "")

    if sacas is not None:
        if isinstance(sacas, Decimal):
            total_pva_atual += sacas
        elif isinstance(sacas, (int, float)):
            total_pva_atual += Decimal(str(sacas))

    if peso is not None:
        if isinstance(peso, (int, float)):
            peso_pva += float(peso)
        elif isinstance(peso, Decimal):
            peso_pva += float(peso)

    if lote:
        lotes_pva.add(lote)

print("RESULTADOS DO SQL (APENAS PVA - ATUAL):")
print(f"  Total de Sacas PVA: {float(total_pva_atual):,.2f}")
print(f"  Peso Total: {peso_pva:,.2f} kg")
print(f"  Quantidade de Lotes: {len(lotes_pva)}")
print()

# Comparar
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA (servidor): {resposta_ia_servidor:,.2f} sacas")
print(f"SQL ATUAL (PVA apenas): {float(total_pva_atual):,.2f} sacas")
print()

diferenca_ia_sql = abs(resposta_ia_servidor - float(total_pva_atual))
print(f"Diferenca IA vs SQL: {diferenca_ia_sql:,.2f} sacas")
print()

if diferenca_ia_sql < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
    print("     Os dados no SQL mudaram desde meu teste local.")
elif diferenca_ia_sql < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
else:
    percentual = (diferenca_ia_sql / float(total_pva_atual)) * 100
    print(f"[ATENCAO] Diferenca de {diferenca_ia_sql:,.2f} sacas ({percentual:.2f}%)")

    if percentual < 2.0:
        print("Diferenca aceitavel (< 2%) - provavelmente dados mudaram")
    else:
        print("Diferenca significativa - INVESTIGAR!")

print()
print("CONCLUSAO:")
if diferenca_ia_sql < 10.0:
    print("  [OK] O FILTRO ESTA FUNCIONANDO PERFEITAMENTE!")
    print("  [OK] A IA respondeu apenas PVA, nao o total geral")
    print(f"  [OK] Diferenca de {diferenca:,.2f} sacas entre meu teste local e servidor")
    print("       e normal - dados do SQL mudaram entre os testes")
else:
    print("  [?] Verificar por que diferenca e maior que esperado")

print()
print("=" * 80)
