"""
Analisa estoque por país (BRASIL vs EUROPA)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("ANALISE: Estoque por pais (BRASIL vs EUROPA)")
print("=" * 80)
print()

# Buscar dados do SQL
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# Separar por país
brasil = []
europa = []
sem_pais = []

for r in results:
    pais = str(r.get("pais", "")).strip().upper()
    if pais == "BRASIL":
        brasil.append(r)
    elif pais == "EUROPA":
        europa.append(r)
    else:
        sem_pais.append(r)

print(f"Registros BRASIL: {len(brasil)}")
print(f"Registros EUROPA: {len(europa)}")
print(f"Registros sem pais: {len(sem_pais)}")
print()

# Calcular totais para BRASIL
total_brasil = Decimal(0)
for r in brasil:
    sacas = r.get("sacas", 0)
    if sacas:
        if isinstance(sacas, Decimal):
            total_brasil += sacas
        else:
            total_brasil += Decimal(str(sacas))

# Calcular totais para EUROPA
total_europa = Decimal(0)
for r in europa:
    sacas = r.get("sacas", 0)
    if sacas:
        if isinstance(sacas, Decimal):
            total_europa += sacas
        else:
            total_europa += Decimal(str(sacas))

# Calcular totais sem país
total_sem_pais = Decimal(0)
for r in sem_pais:
    sacas = r.get("sacas", 0)
    if sacas:
        if isinstance(sacas, Decimal):
            total_sem_pais += sacas
        else:
            total_sem_pais += Decimal(str(sacas))

print("=" * 80)
print("TOTAIS POR PAIS:")
print("=" * 80)
print(f"BRASIL: {float(total_brasil):,.2f} sacas")
print(f"EUROPA: {float(total_europa):,.2f} sacas")
if float(total_sem_pais) > 0:
    print(f"Sem pais: {float(total_sem_pais):,.2f} sacas")
print()

total_geral = total_brasil + total_europa + total_sem_pais
print(f"TOTAL GERAL: {float(total_geral):,.2f} sacas")
print()

# Percentuais
if float(total_geral) > 0:
    perc_brasil = (float(total_brasil) / float(total_geral)) * 100
    perc_europa = (float(total_europa) / float(total_geral)) * 100
    print("DISTRIBUICAO:")
    print(f"  Brasil: {perc_brasil:.1f}%")
    print(f"  Europa: {perc_europa:.1f}%")
    print()

# Análise do erro
print("=" * 80)
print("ANALISE DO ERRO:")
print("=" * 80)
print()
print("PERGUNTA DO USUARIO: 'Quanto cafe brasileiro temos?'")
print(f"RESPOSTA DA IA: 135.131,22 sacas (total geral)")
print()
print(f"RESPOSTA CORRETA DEVERIA SER: {float(total_brasil):,.2f} sacas (apenas BRASIL)")
print()

diferenca = float(total_geral) - float(total_brasil)
print(f"ERRO: A IA incluiu {diferenca:,.2f} sacas europeias na conta!")
print()

print("=" * 80)
print("CONCLUSAO:")
print("=" * 80)
print()
print("[ERRO CRITICO] A IA nao aplicou filtro por pais='BRASIL'")
print("               Respondeu com total geral incluindo Europa")
print()
print("CAUSA PROVAVEL:")
print("  - Filtro de pais nao esta implementado nos filtros automaticos")
print("  - Precisa adicionar deteccao de 'brasileiro', 'brasil' para filtrar pais")
print()

print("=" * 80)
