"""
Valida resposta da IA: "Quanto café Rainforest temos?"
IA respondeu: 78.394,01 sacas com certificado Rainforest (RF)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from dotenv import load_dotenv
from decimal import Decimal

load_dotenv()

print("=" * 80)
print("VALIDACAO: Quanto cafe Rainforest temos?")
print("=" * 80)
print()

# Resposta da IA
resposta_ia = 78394.01
print(f"Resposta da IA: {resposta_ia:,.2f} sacas de cafe Rainforest (RF)")
print()

# Buscar dados do SQL
print("Consultando SQL Server...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"Total de registros (TODOS): {len(results)}")
print()

# Filtrar certificado Rainforest (RF)
# Pode ser "RF" ou "RAINFOREST" no campo certificado
results_rf = []
for r in results:
    certificado = str(r.get("certificado", "")).strip().upper()
    if certificado == "RF" or "RAINFOREST" in certificado:
        results_rf.append(r)

print(f"Total de registros com certificado RF/Rainforest: {len(results_rf)}")
print()

if len(results_rf) == 0:
    print("[ERRO] NAO TEM CAFE RAINFOREST NO ESTOQUE!")
    print("       A IA respondeu ERRADO!")
else:
    # Calcular total Rainforest
    total_rf = Decimal(0)
    total_rf_consumo = Decimal(0)
    total_rf_exportacao = Decimal(0)
    peso_rf = 0.0
    lotes_rf = set()
    linhas_rf = set()
    filiais_rf = set()

    for r in results_rf:
        sacas = r.get("sacas", 0)
        sacas_consumo = r.get("sacasConsumo", 0)
        sacas_exportacao = r.get("sacasExportacao", 0)
        peso = r.get("peso", 0)
        lote = r.get("lote", "")
        linha = r.get("linha", "")
        filial = r.get("filial", "")

        if sacas is not None:
            if isinstance(sacas, Decimal):
                total_rf += sacas
            elif isinstance(sacas, (int, float)):
                total_rf += Decimal(str(sacas))

        if sacas_consumo is not None:
            if isinstance(sacas_consumo, Decimal):
                total_rf_consumo += sacas_consumo
            elif isinstance(sacas_consumo, (int, float)):
                total_rf_consumo += Decimal(str(sacas_consumo))

        if sacas_exportacao is not None:
            if isinstance(sacas_exportacao, Decimal):
                total_rf_exportacao += sacas_exportacao
            elif isinstance(sacas_exportacao, (int, float)):
                total_rf_exportacao += Decimal(str(sacas_exportacao))

        if peso is not None:
            if isinstance(peso, (int, float)):
                peso_rf += float(peso)
            elif isinstance(peso, Decimal):
                peso_rf += float(peso)

        if lote:
            lotes_rf.add(lote)
        if linha:
            linhas_rf.add(linha.strip())
        if filial:
            filiais_rf.add(filial.strip())

    print("RESULTADOS DO SQL (APENAS RAINFOREST/RF):")
    print(f"  Total de Sacas RF: {float(total_rf):,.2f}")
    print(f"  Sacas Consumo: {float(total_rf_consumo):,.2f}")
    print(f"  Sacas Exportacao: {float(total_rf_exportacao):,.2f}")
    print(f"  Peso Total: {peso_rf:,.2f} kg")
    print(f"  Quantidade de Lotes: {len(lotes_rf)}")
    print(f"  Linhas presentes: {', '.join(sorted(linhas_rf))}")
    print(f"  Filiais: {', '.join(sorted(filiais_rf))}")
    print()

    # Comparar com resposta da IA
    print("=" * 80)
    print("COMPARACAO:")
    print("=" * 80)
    print(f"Resposta da IA: {resposta_ia:,.2f} sacas")
    print(f"SQL ATUAL (RF apenas): {float(total_rf):,.2f} sacas")
    print()

    diferenca = abs(resposta_ia - float(total_rf))
    print(f"Diferenca: {diferenca:,.2f} sacas")
    print()

    if diferenca < 1.0:
        print("[OK] RESPOSTA DA IA ESTA CORRETA!")
    elif diferenca < 10.0:
        print("[OK] RESPOSTA DA IA ESTA CORRETA (pequena diferenca de arredondamento)")
    else:
        percentual = (diferenca / float(total_rf)) * 100
        print(f"[ATENCAO] Diferenca de {diferenca:,.2f} sacas ({percentual:.2f}%)")

        if percentual < 2.0:
            print("Diferenca aceitavel (< 2%)")
        else:
            print("Diferenca significativa - INVESTIGAR!")

    print()
    print("CONCLUSAO:")
    if diferenca < 10.0:
        print("  [OK] O FILTRO DE CERTIFICADO ESTA FUNCIONANDO!")
        print("  [OK] A IA identificou 'Rainforest' e filtrou por certificado RF")
        print("  [OK] Resposta precisa e completa")
    else:
        print("  [?] Verificar motivo da diferenca")

print()
print("=" * 80)
