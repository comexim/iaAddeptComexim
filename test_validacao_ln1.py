"""
Valida resposta da IA: "Temos café linha LN1?"
IA respondeu: "Sim, temos café da linha LN1 em estoque."
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Temos cafe linha LN1?")
print("=" * 80)
print()

# Resposta da IA
print("Resposta da IA: 'Sim, temos cafe da linha LN1 em estoque.'")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros (TODOS): {len(results)}")
print()

# Filtrar APENAS LN1
results_ln1 = []
for r in results:
    linha = str(r.get("linha", "")).strip().upper()
    if linha == "LN1":
        results_ln1.append(r)

print(f"Total de registros LN1: {len(results_ln1)}")
print()

if len(results_ln1) == 0:
    print("[ERRO] NAO TEM CAFE LN1 NO ESTOQUE!")
    print("       A IA respondeu ERRADO!")
else:
    # Calcular total LN1
    total_ln1 = Decimal(0)
    total_ln1_consumo = Decimal(0)
    total_ln1_exportacao = Decimal(0)
    peso_ln1 = 0.0
    lotes_ln1 = set()

    for r in results_ln1:
        sacas = r.get("sacas", 0)
        sacas_consumo = r.get("sacasConsumo", 0)
        sacas_exportacao = r.get("sacasExportacao", 0)
        peso = r.get("peso", 0)
        lote = r.get("lote", "")

        if sacas is not None:
            if isinstance(sacas, Decimal):
                total_ln1 += sacas
            elif isinstance(sacas, (int, float)):
                total_ln1 += Decimal(str(sacas))

        if sacas_consumo is not None:
            if isinstance(sacas_consumo, Decimal):
                total_ln1_consumo += sacas_consumo
            elif isinstance(sacas_consumo, (int, float)):
                total_ln1_consumo += Decimal(str(sacas_consumo))

        if sacas_exportacao is not None:
            if isinstance(sacas_exportacao, Decimal):
                total_ln1_exportacao += sacas_exportacao
            elif isinstance(sacas_exportacao, (int, float)):
                total_ln1_exportacao += Decimal(str(sacas_exportacao))

        if peso is not None:
            if isinstance(peso, (int, float)):
                peso_ln1 += float(peso)
            elif isinstance(peso, Decimal):
                peso_ln1 += float(peso)

        if lote:
            lotes_ln1.add(lote)

    print("RESULTADOS DO SQL (APENAS LN1):")
    print(f"  Total de Sacas LN1: {float(total_ln1):,.2f}")
    print(f"  Sacas Consumo: {float(total_ln1_consumo):,.2f}")
    print(f"  Sacas Exportacao: {float(total_ln1_exportacao):,.2f}")
    print(f"  Peso Total: {peso_ln1:,.2f} kg")
    print(f"  Quantidade de Lotes: {len(lotes_ln1)}")
    print()

    print("=" * 80)
    print("AVALIACAO DA RESPOSTA:")
    print("=" * 80)
    print()

    print("[OK] A IA respondeu CORRETAMENTE que tem cafe LN1!")
    print()

    print("POREM, a resposta poderia ser MAIS INFORMATIVA:")
    print(f"  Resposta ideal: 'Sim, temos {float(total_ln1):,.2f} sacas de cafe linha LN1 em estoque.'")
    print()

    print("ANALISE:")
    print("  - A IA confirmou que tem LN1: [OK]")
    print("  - Mas nao disse QUANTAS sacas: [INCOMPLETO]")
    print()

    if float(total_ln1) > 0:
        print("[CONCLUSAO] Resposta CORRETA mas INCOMPLETA")
        print("            A IA deveria ter mencionado a quantidade")
    else:
        print("[ERRO] Tem registros mas quantidade e zero!")

print()
print("=" * 80)
