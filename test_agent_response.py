"""
Simula exatamente o que o agente SQL retorna para a IA
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict
from decimal import Decimal
import json

def aggregate_orcamento(results):
    """Replica a lógica de _aggregate_orcamento()"""
    aggregated = defaultdict(lambda: {
        "orcado": 0,
        "realizado": 0,
        "saldo": 0,
        "registros": 0
    })

    for row in results:
        grupo = row.get("grupo", "SEM GRUPO")
        descricao = row.get("descricao", "").strip()
        key = descricao if descricao else grupo

        aggregated[key]["orcado"] += row.get("orcado", 0) or 0
        aggregated[key]["realizado"] += row.get("realizado", 0) or 0
        aggregated[key]["saldo"] += row.get("saldo", 0) or 0
        aggregated[key]["registros"] += 1

    result_list = []
    for categoria, data in aggregated.items():
        percentual = 0
        if data["orcado"] > 0:
            percentual = round((data["realizado"] / data["orcado"]) * 100, 2)

        result_list.append({
            "categoria": categoria,
            "orcado": round(data["orcado"], 2),
            "realizado": round(data["realizado"], 2),
            "saldo": round(data["saldo"], 2),
            "percentual_realizado": percentual,
            "meses_incluidos": data["registros"]
        })

    result_list.sort(key=lambda x: x["orcado"], reverse=True)
    return result_list

def test_agent_response():
    """Simula chamada do agente para orçamento janeiro 2026"""
    print("=" * 80)
    print("SIMULACAO DO AGENTE SQL - 'orcamento janeiro 2026'")
    print("=" * 80)

    try:
        print("\n1. Conectando e consultando banco...\n")
        filters = {"ano": 2026, "mes": "01"}
        results = sql_client.execute_function("IA_Orcamento", filters)

        print(f"Registros SQL: {len(results)}")

        print("\n2. Agregando dados...")
        aggregated = aggregate_orcamento(results)

        print(f"Categorias agregadas: {len(aggregated)}")

        # Converte para JSON (como o agente faz)
        def convert_decimals(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        # CALCULA TOTAIS (não deixa a IA somar manualmente para evitar erros)
        total_orcado = sum(item.get("orcado", 0) for item in aggregated)
        total_realizado = sum(item.get("realizado", 0) for item in aggregated)
        total_saldo = sum(item.get("saldo", 0) for item in aggregated)
        percentual_total = round((total_realizado / total_orcado) * 100, 2) if total_orcado > 0 else 0

        formatted = json.dumps(aggregated, ensure_ascii=False, indent=2, default=convert_decimals)

        # Monta a resposta completa (como o agente faz AGORA)
        response = f"""Resultados da consulta IA_Orcamento (AGREGADOS POR CATEGORIA):

Total de registros SQL: {len(results)}
Total de categorias: {len(aggregated)}

TOTAIS GERAIS (PRE-CALCULADOS):
- Total Orcado: R$ {total_orcado:,.2f}
- Total Realizado: R$ {total_realizado:,.2f}
- Total Saldo: R$ {total_saldo:,.2f}
- Percentual Realizado: {percentual_total}%

Dados por categoria:
{formatted}

Instruções: Os dados acima são de ORÇAMENTO (budget vs realizado).

CAMPOS DISPONÍVEIS POR CATEGORIA:
- categoria: nome da categoria/grupo orçamentário
- orcado: valor orçado desta categoria (R$)
- realizado: valor realizado desta categoria (R$)
- saldo: saldo desta categoria (R$)
- percentual_realizado: percentual realizado desta categoria (%)
- meses_incluidos: quantidade de registros agregados

IMPORTANTE:
1. Orçamento NÃO tem contratos, sacas ou clientes. É uma previsão financeira.
2. Para totais gerais, USE OS VALORES PRE-CALCULADOS acima. NÃO some manualmente.
3. Os "TOTAIS GERAIS" já incluem TODAS as categorias somadas.

Exemplos de perguntas:
- "Qual o orçado total?" → Use "Total Orcado" dos TOTAIS GERAIS
- "Quanto foi realizado?" → Use "Total Realizado" dos TOTAIS GERAIS
- "Qual categoria teve maior gasto?" → Ordene as categorias por "realizado"
- "Qual o percentual realizado?" → Use "Percentual Realizado" dos TOTAIS GERAIS"""

        # Salva response em arquivo para evitar problemas de encoding
        with open("agent_response.txt", "w", encoding="utf-8") as f:
            f.write(response)

        print("\n=" * 80)
        print("3. RESPOSTA COMPLETA salva em 'agent_response.txt'")
        print("=" * 80)

        # Analisa os valores
        print("\n\n4. ANALISE DOS VALORES:")
        print("-" * 80)

        # Calcula totais
        total_orcado = sum(item.get("orcado", 0) for item in aggregated)
        total_realizado = sum(item.get("realizado", 0) for item in aggregated)
        total_saldo = sum(item.get("saldo", 0) for item in aggregated)

        print(f"\nSE A IA SOMAR CORRETAMENTE:")
        print(f"  Total Orcado: R$ {total_orcado:,.2f}")
        print(f"  Total Realizado: R$ {total_realizado:,.2f}")
        print(f"  Total Saldo: R$ {total_saldo:,.2f}")

        print(f"\nO QUE A IA DISSE:")
        print(f"  Total Orcado: R$ 14.351.969,81")
        print(f"  Total Realizado: R$ 5.191.484,92")
        print(f"  Total Saldo: R$ 9.160.484,89")

        print(f"\nDIFERENCA NO ORCADO:")
        diferenca = 14351969.81 - total_orcado
        print(f"  R$ {diferenca:,.2f}")

        # Mostra top 5 categorias
        print(f"\nTOP 5 CATEGORIAS (orcado):")
        for i, item in enumerate(aggregated[:5], 1):
            print(f"  {i}. {item['categoria']}: R$ {item['orcado']:,.2f}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_agent_response()
