"""
Valida resposta da IA: "Qual tipo de café temos mais?"
IA respondeu: GRD com 42.459,95 sacas
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal
from collections import defaultdict

load_dotenv()

print("=" * 80)
print("VALIDACAO: Qual tipo de cafe temos mais?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia_linha = "GRD"
resposta_ia_sacas = 42459.95
print(f"Resposta da IA: {resposta_ia_linha} com {resposta_ia_sacas:,.2f} sacas")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# Agregar por linha
print("=" * 80)
print("AGREGACAO POR LINHA (todas as linhas):")
print("=" * 80)

sacas_por_linha = defaultdict(lambda: Decimal(0))

for r in results:
    linha = str(r.get("linha", "SEM LINHA")).strip() or "SEM LINHA"
    sacas = r.get("sacas", 0)

    if sacas is not None:
        if isinstance(sacas, Decimal):
            sacas_por_linha[linha] += sacas
        elif isinstance(sacas, (int, float)):
            sacas_por_linha[linha] += Decimal(str(sacas))

# Ordenar por quantidade (maior para menor)
linhas_ordenadas = sorted(sacas_por_linha.items(), key=lambda x: x[1], reverse=True)

print(f"Total de linhas diferentes: {len(linhas_ordenadas)}")
print()

print("Ranking de sacas por linha:")
for i, (linha, sacas) in enumerate(linhas_ordenadas, 1):
    print(f"  {i}. {linha}: {float(sacas):,.2f} sacas")
print()

# Identificar a linha com mais sacas
linha_maior = linhas_ordenadas[0][0]
sacas_maior = float(linhas_ordenadas[0][1])

print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA: {resposta_ia_linha} com {resposta_ia_sacas:,.2f} sacas")
print(f"SQL (maior linha): {linha_maior} com {sacas_maior:,.2f} sacas")
print()

if linha_maior == resposta_ia_linha:
    diferenca = abs(sacas_maior - resposta_ia_sacas)
    print(f"Diferenca: {diferenca:,.2f} sacas")
    print()

    if diferenca < 1.0:
        print("[OK] RESPOSTA DA IA ESTA CORRETA!")
        print(f"     {linha_maior} e realmente a linha com mais sacas em estoque")
    elif diferenca < 10.0:
        print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
        print(f"     {linha_maior} e realmente a linha com mais sacas em estoque")
    else:
        print(f"[ATENCAO] Linha correta mas diferenca de {diferenca:,.2f} sacas")
else:
    print(f"[ERRO] IA respondeu {resposta_ia_linha}, mas a linha com mais sacas e {linha_maior}!")
    print(f"       {linha_maior} tem {sacas_maior:,.2f} sacas")
    print(f"       {resposta_ia_linha} tem {float(sacas_por_linha[resposta_ia_linha]):,.2f} sacas")
    print(f"       Diferenca: {sacas_maior - float(sacas_por_linha[resposta_ia_linha]):,.2f} sacas")

print()
print("=" * 80)
