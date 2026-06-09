"""
Valida resposta da IA: "Quanto café disponível para exportar?"
IA respondeu: 113.113,10 sacas disponíveis para exportação
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quanto cafe disponivel para exportar?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia = 113113.10
print(f"Resposta da IA: {resposta_ia:,.2f} sacas para exportacao")
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
registros_com_export = 0
registros_sem_export = 0

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

        # Contar registros
        valor_export = float(sacas_exportacao) if isinstance(sacas_exportacao, Decimal) else sacas_exportacao
        if valor_export > 0:
            registros_com_export += 1
        else:
            registros_sem_export += 1

print("RESULTADOS DO SQL:")
print(f"  Total de Sacas (geral): {float(total_sacas):,.2f}")
print(f"  Sacas para Consumo: {float(total_sacas_consumo):,.2f}")
print(f"  Sacas para Exportacao: {float(total_sacas_exportacao):,.2f}")
print()
print(f"  Registros com sacasExportacao > 0: {registros_com_export}")
print(f"  Registros com sacasExportacao = 0: {registros_sem_export}")
print()

# Verificar equação
soma = total_sacas_consumo + total_sacas_exportacao
print("VALIDACAO DA EQUACAO:")
print(f"  sacasConsumo + sacasExportacao = {float(soma):,.2f}")
print(f"  sacas (total) = {float(total_sacas):,.2f}")
diferenca_eq = abs(float(total_sacas) - float(soma))
print(f"  Diferenca: {diferenca_eq:,.2f}")
if diferenca_eq < 1.0:
    print("  [OK] Equacao validada!")
else:
    print(f"  [ATENCAO] Diferenca de {diferenca_eq:,.2f} sacas (problema nos dados SQL)")
print()

# Comparar com resposta da IA
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print(f"SQL ATUAL (sacasExportacao total): {float(total_sacas_exportacao):,.2f} sacas")
print()

diferenca = abs(resposta_ia - float(total_sacas_exportacao))
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

if diferenca < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
elif diferenca < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
else:
    percentual = (diferenca / float(total_sacas_exportacao)) * 100
    print(f"[ATENCAO] Diferenca de {diferenca:,.2f} sacas ({percentual:.2f}%)")

    if percentual < 2.0:
        print("Diferenca aceitavel (< 2%)")
    else:
        print("Diferenca significativa - INVESTIGAR!")

print()
print("CONCLUSAO:")
if diferenca < 10.0:
    print("  [OK] O FILTRO DE EXPORTACAO ESTA FUNCIONANDO!")
    print("  [OK] A IA identificou 'exportar' e somou campo sacasExportacao")
    print("  [OK] Resposta precisa e completa")
    print()
    print(f"  NOTA: {float(total_sacas_consumo):,.2f} sacas sao para consumo interno")
    print(f"        {float(total_sacas_exportacao):,.2f} sacas sao para exportacao")
    print(f"        Total: {float(total_sacas):,.2f} sacas")
else:
    print("  [?] Verificar motivo da diferenca")

print()
print("=" * 80)
