"""
Valida resposta da IA: "Sacas de GRD disponíveis para consumo?"
IA respondeu: 2.697,66 sacas de GRD para consumo
TESTE DE FILTROS COMBINADOS: linha=GRD + destino=consumo
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Sacas de GRD disponiveis para consumo?")
print("=" * 80)
print()

# Resposta da IA (APÓS FIX)
resposta_ia = 7159.49
print(f"Resposta da IA (APÓS FIX): {resposta_ia:,.2f} sacas de GRD para consumo")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros (TODOS): {len(results)}")
print()

# PASSO 1: Filtrar apenas GRD
results_grd = []
for r in results:
    linha = str(r.get("linha", "")).strip().upper()
    if linha == "GRD":
        results_grd.append(r)

print(f"Total de registros GRD: {len(results_grd)}")
print()

# PASSO 2: Calcular totais do GRD
total_grd_todas = Decimal(0)
total_grd_consumo = Decimal(0)
total_grd_exportacao = Decimal(0)
peso_grd = 0.0
lotes_grd = set()

for r in results_grd:
    sacas = r.get("sacas", 0)
    sacas_consumo = r.get("sacasConsumo", 0)
    sacas_exportacao = r.get("sacasExportacao", 0)
    peso = r.get("peso", 0)
    lote = r.get("lote", "")

    if sacas is not None:
        if isinstance(sacas, Decimal):
            total_grd_todas += sacas
        elif isinstance(sacas, (int, float)):
            total_grd_todas += Decimal(str(sacas))

    if sacas_consumo is not None:
        if isinstance(sacas_consumo, Decimal):
            total_grd_consumo += sacas_consumo
        elif isinstance(sacas_consumo, (int, float)):
            total_grd_consumo += Decimal(str(sacas_consumo))

    if sacas_exportacao is not None:
        if isinstance(sacas_exportacao, Decimal):
            total_grd_exportacao += sacas_exportacao
        elif isinstance(sacas_exportacao, (int, float)):
            total_grd_exportacao += Decimal(str(sacas_exportacao))

    if peso is not None:
        if isinstance(peso, (int, float)):
            peso_grd += float(peso)
        elif isinstance(peso, Decimal):
            peso_grd += float(peso)

    if lote:
        lotes_grd.add(lote)

print("RESULTADOS DO SQL (GRD):")
print(f"  Total de Sacas GRD (todas): {float(total_grd_todas):,.2f}")
print(f"  Sacas GRD para Consumo: {float(total_grd_consumo):,.2f}")
print(f"  Sacas GRD para Exportacao: {float(total_grd_exportacao):,.2f}")
print(f"  Peso Total GRD: {peso_grd:,.2f} kg")
print(f"  Quantidade de Lotes GRD: {len(lotes_grd)}")
print()

# Calcular percentuais
if float(total_grd_todas) > 0:
    percentual_consumo = (float(total_grd_consumo) / float(total_grd_todas)) * 100
    percentual_export = (float(total_grd_exportacao) / float(total_grd_todas)) * 100
    print("DISTRIBUICAO DO GRD:")
    print(f"  Consumo: {percentual_consumo:.1f}% do GRD")
    print(f"  Exportacao: {percentual_export:.1f}% do GRD")
    print()

# Comparar com resposta da IA
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print(f"SQL ATUAL (GRD + sacasConsumo): {float(total_grd_consumo):,.2f} sacas")
print()

diferenca = abs(resposta_ia - float(total_grd_consumo))
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

if diferenca < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
elif diferenca < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
else:
    percentual = (diferenca / float(total_grd_consumo)) * 100 if float(total_grd_consumo) > 0 else 0
    print(f"[ATENCAO] Diferenca de {diferenca:,.2f} sacas ({percentual:.2f}%)")

    if percentual < 2.0:
        print("Diferenca aceitavel (< 2%)")
    else:
        print("Diferenca significativa - INVESTIGAR!")

print()
print("=" * 80)
print("CONCLUSAO:")
print("=" * 80)
if diferenca < 10.0:
    print("  [OK] FILTROS COMBINADOS ESTAO FUNCIONANDO PERFEITAMENTE!")
    print("  [OK] A IA aplicou DOIS filtros simultaneamente:")
    print("       1. Filtro por linha: GRD")
    print("       2. Filtro por destino: consumo (sacasConsumo)")
    print("  [OK] Resposta precisa e completa")
    print()
    print("  NOTA: Este teste valida que a IA consegue combinar")
    print("        multiplos filtros na mesma query!")
else:
    print("  [?] Verificar motivo da diferenca")

print()
print("=" * 80)
