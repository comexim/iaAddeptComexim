"""
Valida resposta da IA: "Temos mais café para exportação ou consumo?"
IA respondeu: Exportação 113.113,10 | Consumo 11.022,11
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Temos mais cafe para exportacao ou consumo?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia_exportacao = 113113.10
resposta_ia_consumo = 11022.11
print(f"Resposta da IA:")
print(f"  Exportacao: {resposta_ia_exportacao:,.2f} sacas")
print(f"  Consumo: {resposta_ia_consumo:,.2f} sacas")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# Calcular totais
total_sacas = Decimal(0)
total_sacas_consumo = Decimal(0)
total_sacas_exportacao = Decimal(0)

for r in results:
    sacas = r.get("sacas", 0)
    sacas_consumo = r.get("sacasConsumo", 0)
    sacas_exportacao = r.get("sacasExportacao", 0)

    if sacas is not None:
        if isinstance(sacas, Decimal):
            total_sacas += sacas
        elif isinstance(sacas, (int, float)):
            total_sacas += Decimal(str(sacas))

    if sacas_consumo is not None:
        if isinstance(sacas_consumo, Decimal):
            total_sacas_consumo += sacas_consumo
        elif isinstance(sacas_consumo, (int, float)):
            total_sacas_consumo += Decimal(str(sacas_consumo))

    if sacas_exportacao is not None:
        if isinstance(sacas_exportacao, Decimal):
            total_sacas_exportacao += sacas_exportacao
        elif isinstance(sacas_exportacao, (int, float)):
            total_sacas_exportacao += Decimal(str(sacas_exportacao))

print("RESULTADOS DO SQL:")
print(f"  Total de Sacas (geral): {float(total_sacas):,.2f}")
print(f"  Sacas para Consumo: {float(total_sacas_consumo):,.2f}")
print(f"  Sacas para Exportacao: {float(total_sacas_exportacao):,.2f}")
print()

# Verificar qual é maior
if float(total_sacas_exportacao) > float(total_sacas_consumo):
    maior = "EXPORTACAO"
    diferenca = float(total_sacas_exportacao) - float(total_sacas_consumo)
    percentual_maior = (float(total_sacas_exportacao) / float(total_sacas)) * 100
    percentual_menor = (float(total_sacas_consumo) / float(total_sacas)) * 100
else:
    maior = "CONSUMO"
    diferenca = float(total_sacas_consumo) - float(total_sacas_exportacao)
    percentual_maior = (float(total_sacas_consumo) / float(total_sacas)) * 100
    percentual_menor = (float(total_sacas_exportacao) / float(total_sacas)) * 100

print("ANALISE:")
print(f"  Temos MAIS cafe para: {maior}")
print(f"  Diferenca: {diferenca:,.2f} sacas")
print(f"  Exportacao: {percentual_maior:.1f}% do total" if maior == "EXPORTACAO" else f"  Exportacao: {percentual_menor:.1f}% do total")
print(f"  Consumo: {percentual_menor:.1f}% do total" if maior == "EXPORTACAO" else f"  Consumo: {percentual_maior:.1f}% do total")
print()

# Comparar com resposta da IA
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"IA - Exportacao: {resposta_ia_exportacao:,.2f} sacas")
print(f"SQL - Exportacao: {float(total_sacas_exportacao):,.2f} sacas")
print(f"Diferenca: {abs(resposta_ia_exportacao - float(total_sacas_exportacao)):,.2f} sacas")
print()
print(f"IA - Consumo: {resposta_ia_consumo:,.2f} sacas")
print(f"SQL - Consumo: {float(total_sacas_consumo):,.2f} sacas")
print(f"Diferenca: {abs(resposta_ia_consumo - float(total_sacas_consumo)):,.2f} sacas")
print()

# Validação
diferenca_exportacao = abs(resposta_ia_exportacao - float(total_sacas_exportacao))
diferenca_consumo = abs(resposta_ia_consumo - float(total_sacas_consumo))

print("=" * 80)
print("RESULTADO:")
print("=" * 80)

exportacao_ok = diferenca_exportacao < 1.0
consumo_ok = diferenca_consumo < 1.0

if exportacao_ok:
    print("[OK] Valor de exportacao CORRETO!")
else:
    print(f"[ERRO] Valor de exportacao INCORRETO! Diferenca: {diferenca_exportacao:,.2f} sacas")

if consumo_ok:
    print("[OK] Valor de consumo CORRETO!")
else:
    print(f"[ERRO] Valor de consumo INCORRETO! Diferenca: {diferenca_consumo:,.2f} sacas")
    print(f"      IA respondeu: {resposta_ia_consumo:,.2f}")
    print(f"      Valor correto: {float(total_sacas_consumo):,.2f}")
print()

# Verificar se conclusão está correta
ia_disse_exportacao_maior = resposta_ia_exportacao > resposta_ia_consumo
real_exportacao_maior = float(total_sacas_exportacao) > float(total_sacas_consumo)

if ia_disse_exportacao_maior == real_exportacao_maior:
    print("[OK] IA respondeu CORRETAMENTE que temos mais para EXPORTACAO")
else:
    print("[ERRO] IA errou a conclusao sobre qual categoria tem mais!")

print()
print("=" * 80)
