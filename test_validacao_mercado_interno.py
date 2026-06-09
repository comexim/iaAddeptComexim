"""
Valida resposta da IA: "Quanto café temos para mercado interno?"
IA respondeu: 22.015,81 sacas para mercado interno
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quanto cafe temos para mercado interno?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia = 22015.81
print(f"Resposta da IA: {resposta_ia:,.2f} sacas para mercado interno")
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
registros_com_consumo = 0
registros_sem_consumo = 0

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

        # Contar registros
        valor_consumo = float(sacas_consumo) if isinstance(sacas_consumo, Decimal) else sacas_consumo
        if valor_consumo > 0:
            registros_com_consumo += 1
        else:
            registros_sem_consumo += 1

    if sacas_exportacao is not None:
        if isinstance(sacas_exportacao, Decimal):
            total_sacas_exportacao += sacas_exportacao
        elif isinstance(sacas_exportacao, (int, float)):
            total_sacas_exportacao += Decimal(str(sacas_exportacao))

print("RESULTADOS DO SQL:")
print(f"  Total de Sacas (geral): {float(total_sacas):,.2f}")
print(f"  Sacas para Consumo (mercado interno): {float(total_sacas_consumo):,.2f}")
print(f"  Sacas para Exportacao: {float(total_sacas_exportacao):,.2f}")
print()
print(f"  Registros com sacasConsumo > 0: {registros_com_consumo}")
print(f"  Registros com sacasConsumo = 0: {registros_sem_consumo}")
print()

# Verificar percentual
percentual_consumo = (float(total_sacas_consumo) / float(total_sacas)) * 100
percentual_export = (float(total_sacas_exportacao) / float(total_sacas)) * 100

print("DISTRIBUICAO:")
print(f"  Consumo interno: {percentual_consumo:.1f}% do total")
print(f"  Exportacao: {percentual_export:.1f}% do total")
print()

# Comparar com resposta da IA
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print(f"SQL ATUAL (sacasConsumo total): {float(total_sacas_consumo):,.2f} sacas")
print()

diferenca = abs(resposta_ia - float(total_sacas_consumo))
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

if diferenca < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
elif diferenca < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
else:
    percentual = (diferenca / float(total_sacas_consumo)) * 100
    print(f"[ATENCAO] Diferenca de {diferenca:,.2f} sacas ({percentual:.2f}%)")

    if percentual < 2.0:
        print("Diferenca aceitavel (< 2%)")
    else:
        print("Diferenca significativa - INVESTIGAR!")

print()
print("CONCLUSAO:")
if diferenca < 10.0:
    print("  [OK] O FILTRO DE MERCADO INTERNO/CONSUMO ESTA FUNCIONANDO!")
    print("  [OK] A IA identificou 'mercado interno' e somou campo sacasConsumo")
    print("  [OK] Resposta precisa e completa")
    print()
    print("  RESUMO DO ESTOQUE:")
    print(f"    - Mercado interno: {float(total_sacas_consumo):,.2f} sacas ({percentual_consumo:.1f}%)")
    print(f"    - Exportacao: {float(total_sacas_exportacao):,.2f} sacas ({percentual_export:.1f}%)")
    print(f"    - TOTAL: {float(total_sacas):,.2f} sacas")
else:
    print("  [?] Verificar motivo da diferenca")

print()
print("=" * 80)
