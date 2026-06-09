"""
Valida resposta da IA: "Quanto café brasileiro temos?"
IA respondeu: 135.131,22 sacas
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quanto cafe brasileiro temos?")
print("=" * 80)
print()

# Resposta da IA (APÓS FIX)
resposta_ia = 134050.04
print(f"Resposta da IA (APÓS FIX): {resposta_ia:,.2f} sacas de cafe brasileiro")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros: {len(results)}")
print()

# Verificar se existe campo de origem/país
print("=" * 80)
print("ANALISE: Existe campo de origem/pais no banco?")
print("=" * 80)

if results:
    campos = results[0].keys()
    print(f"Campos disponiveis: {', '.join(campos)}")
    print()

    campos_origem = [c for c in campos if any(termo in c.lower() for termo in ["origem", "pais", "country", "origin"])]

    if campos_origem:
        print(f"[INFO] Campos de origem encontrados: {', '.join(campos_origem)}")
        print()

        # Verificar valores únicos
        for campo in campos_origem:
            valores = set(str(r.get(campo, "")).strip() for r in results if r.get(campo))
            print(f"  Valores em '{campo}': {', '.join(sorted(valores))}")
    else:
        print("[INFO] NAO existe campo de origem/pais no banco")
        print("       Isso significa que TODO o cafe no estoque e brasileiro")
        print()

# Calcular total de sacas
print("=" * 80)
print("CALCULO DO TOTAL:")
print("=" * 80)

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

print(f"Total de Sacas (campo 'sacas'): {float(total_sacas):,.2f}")
print(f"Total Consumo (campo 'sacasConsumo'): {float(total_sacas_consumo):,.2f}")
print(f"Total Exportacao (campo 'sacasExportacao'): {float(total_sacas_exportacao):,.2f}")
print(f"Soma (Consumo + Exportacao): {float(total_sacas_consumo + total_sacas_exportacao):,.2f}")
print()

# Comparar
print("=" * 80)
print("COMPARACAO:")
print("=" * 80)
print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
print(f"SQL (total campo 'sacas'): {float(total_sacas):,.2f} sacas")
print()

diferenca = abs(resposta_ia - float(total_sacas))
print(f"Diferenca: {diferenca:,.2f} sacas")
print()

# Se a diferença for grande, ver se IA usou Consumo+Exportacao
diferenca_soma = abs(resposta_ia - float(total_sacas_consumo + total_sacas_exportacao))

if diferenca < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
    print("     IA usou o campo 'sacas' (total geral)")
elif diferenca < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
    print("     IA usou o campo 'sacas' (total geral)")
elif diferenca_soma < 1.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA!")
    print("     IA usou a soma de 'sacasConsumo' + 'sacasExportacao'")
    print(f"     Soma: {float(total_sacas_consumo + total_sacas_exportacao):,.2f}")
elif diferenca_soma < 10.0:
    print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
    print("     IA usou a soma de 'sacasConsumo' + 'sacasExportacao'")
    print(f"     Soma: {float(total_sacas_consumo + total_sacas_exportacao):,.2f}")
else:
    print(f"[ATENCAO] Diferenca significativa!")
    print(f"  Diferenca para campo 'sacas': {diferenca:,.2f}")
    print(f"  Diferenca para soma (Consumo+Exportacao): {diferenca_soma:,.2f}")

print()
print("=" * 80)
print("CONCLUSAO:")
print("=" * 80)
print()
if not campos_origem:
    print("NAO existe campo de origem no banco de dados.")
    print("TODO o cafe no estoque da Comexim e brasileiro.")
    print()
    if diferenca < 10.0 or diferenca_soma < 10.0:
        print("[OK] A IA respondeu corretamente com o total de cafe (brasileiro).")
    else:
        print("[?] Verificar motivo da diferenca")
else:
    print("Existe campo de origem - analisar valores")

print()
print("=" * 80)
