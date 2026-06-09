"""
Valida resposta da IA: "Quantas sacas temos em estoque?"
IA respondeu: 137.826,57 sacas
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quantas sacas temos em estoque?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia = 137826.57
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print()

# Buscar dados direto do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# Calcular total de sacas
total_sacas = Decimal(0)
total_sacas_consumo = Decimal(0)
total_sacas_exportacao = Decimal(0)
total_peso = 0.0

for r in results:
    sacas = r.get("sacas", 0)
    sacas_consumo = r.get("sacasConsumo", 0)
    sacas_exportacao = r.get("sacasExportacao", 0)
    peso = r.get("peso", 0)

    # Converter para Decimal se necessário
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

    if peso is not None:
        if isinstance(peso, (int, float)):
            total_peso += float(peso)
        elif isinstance(peso, Decimal):
            total_peso += float(peso)

print("RESULTADOS DO SQL:")
print(f"  Total de Sacas: {float(total_sacas):,.2f}")
print(f"  Sacas Consumo: {float(total_sacas_consumo):,.2f}")
print(f"  Sacas Exportacao: {float(total_sacas_exportacao):,.2f}")
print(f"  Peso Total: {total_peso:,.2f} kg")
print()

# Verificar equacao
soma_consumo_export = total_sacas_consumo + total_sacas_exportacao
print("VALIDACAO DA EQUACAO:")
print(f"  sacasConsumo + sacasExportacao = {float(soma_consumo_export):,.2f}")
print(f"  sacas (total) = {float(total_sacas):,.2f}")
diferenca_equacao = abs(float(total_sacas) - float(soma_consumo_export))
print(f"  Diferenca: {diferenca_equacao:,.2f}")

if diferenca_equacao < 0.01:
    print("  [OK] Equacao validada!")
else:
    print(f"  [ATENCAO] Diferenca de {diferenca_equacao:,.2f} sacas")
print()

# Comparar com resposta da IA
print("COMPARACAO COM IA:")
print(f"  Resposta da IA: {resposta_ia:,.2f} sacas")
print(f"  Total SQL: {float(total_sacas):,.2f} sacas")
diferenca = abs(resposta_ia - float(total_sacas))
print(f"  Diferenca: {diferenca:,.2f} sacas")
print()

if diferenca < 0.01:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
elif diferenca < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (diferenca minima de arredondamento)")
else:
    percentual = (diferenca / float(total_sacas)) * 100
    print(f"[ATENCAO] Diferenca de {diferenca:,.2f} sacas ({percentual:.2f}%)")

    if percentual < 0.1:
        print("Diferenca aceitavel (< 0.1%)")
    else:
        print("Diferenca significativa - INVESTIGAR!")

print()
print("=" * 80)
