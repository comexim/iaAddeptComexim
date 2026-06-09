"""
Valida resposta da IA: "Quanto café PVA temos em estoque?"
IA respondeu: 137.826,57 sacas (total geral)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quanto cafe PVA temos em estoque?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia = 137826.57
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print()

# Buscar dados direto do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros (TODOS): {len(results)}")
print()

# Calcular total GERAL
total_geral = Decimal(0)
for r in results:
    sacas = r.get("sacas", 0)
    if sacas is not None:
        if isinstance(sacas, Decimal):
            total_geral += sacas
        elif isinstance(sacas, (int, float)):
            total_geral += Decimal(str(sacas))

print(f"Total GERAL (todas as linhas): {float(total_geral):,.2f} sacas")
print()

# Filtrar APENAS PVA
print("Filtrando APENAS cafe PVA...")
results_pva = [r for r in results if str(r.get("linha", "")).upper() == "PVA"]
print(f"Total de registros PVA: {len(results_pva)}")
print()

# Calcular total PVA
total_pva = Decimal(0)
total_pva_consumo = Decimal(0)
total_pva_exportacao = Decimal(0)
peso_pva = 0.0
lotes_pva = set()

for r in results_pva:
    sacas = r.get("sacas", 0)
    sacas_consumo = r.get("sacasConsumo", 0)
    sacas_exportacao = r.get("sacasExportacao", 0)
    peso = r.get("peso", 0)
    lote = r.get("lote", "")

    if sacas is not None:
        if isinstance(sacas, Decimal):
            total_pva += sacas
        elif isinstance(sacas, (int, float)):
            total_pva += Decimal(str(sacas))

    if sacas_consumo is not None:
        if isinstance(sacas_consumo, Decimal):
            total_pva_consumo += sacas_consumo
        elif isinstance(sacas_consumo, (int, float)):
            total_pva_consumo += Decimal(str(sacas_consumo))

    if sacas_exportacao is not None:
        if isinstance(sacas_exportacao, Decimal):
            total_pva_exportacao += sacas_exportacao
        elif isinstance(sacas_exportacao, (int, float)):
            total_pva_exportacao += Decimal(str(sacas_exportacao))

    if peso is not None:
        if isinstance(peso, (int, float)):
            peso_pva += float(peso)
        elif isinstance(peso, Decimal):
            peso_pva += float(peso)

    if lote:
        lotes_pva.add(lote)

print("RESULTADOS DO SQL (APENAS PVA):")
print(f"  Total de Sacas PVA: {float(total_pva):,.2f}")
print(f"  Sacas Consumo: {float(total_pva_consumo):,.2f}")
print(f"  Sacas Exportacao: {float(total_pva_exportacao):,.2f}")
print(f"  Peso Total: {peso_pva:,.2f} kg")
print(f"  Quantidade de Lotes: {len(lotes_pva)}")
print()

# Distribuicao por linha
print("DISTRIBUICAO POR LINHA (top 10):")
from collections import defaultdict
por_linha = defaultdict(lambda: {"sacas": Decimal(0), "registros": 0})

for r in results:
    linha = r.get("linha", "").strip() or "SEM LINHA"
    sacas = r.get("sacas", 0)

    if sacas is not None:
        if isinstance(sacas, Decimal):
            por_linha[linha]["sacas"] += sacas
        elif isinstance(sacas, (int, float)):
            por_linha[linha]["sacas"] += Decimal(str(sacas))

    por_linha[linha]["registros"] += 1

# Ordena por sacas
linhas_ordenadas = sorted(por_linha.items(), key=lambda x: x[1]["sacas"], reverse=True)

for i, (linha, dados) in enumerate(linhas_ordenadas[:10], 1):
    print(f"  {i}. {linha}: {float(dados['sacas']):,.2f} sacas ({dados['registros']} lotes)")

print()

# Comparar com resposta da IA
print("=" * 80)
print("ANALISE DA RESPOSTA DA IA:")
print("=" * 80)
print()
print(f"A IA respondeu: {resposta_ia:,.2f} sacas")
print(f"Total GERAL: {float(total_geral):,.2f} sacas")
print(f"Total PVA: {float(total_pva):,.2f} sacas")
print()

# Verificar se IA deu total geral ou total PVA
if abs(resposta_ia - float(total_geral)) < 1.0:
    print("[ERRO] A IA respondeu o TOTAL GERAL, nao apenas PVA!")
    print(f"       Erro: {abs(resposta_ia - float(total_pva)):,.2f} sacas")
    percentual_erro = (abs(resposta_ia - float(total_pva)) / float(total_pva)) * 100
    print(f"       Erro percentual: {percentual_erro:.1f}%")
    print()
    print("RESPOSTA CORRETA deveria ser:")
    print(f"  'Temos {float(total_pva):,.2f} sacas de cafe PVA em estoque.'")
elif abs(resposta_ia - float(total_pva)) < 1.0:
    print("[OK] A IA respondeu corretamente apenas o total PVA!")
else:
    print("[?] Valor nao bate com nenhum total conhecido")

print()
print("=" * 80)
