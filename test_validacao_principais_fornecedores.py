"""
Validação: Quais os principais fornecedores que preciso pagar?
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict
from datetime import datetime

def test_validacao():
    """Valida resposta da IA sobre principais fornecedores"""
    print("=" * 80)
    print("VALIDACAO - Quais os principais fornecedores que preciso pagar?")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        fornecedores_ia = {
            "FOLHA": 51846684.97,
            "COOP. TRES PONTAS": 19567999.98,
            "JUROS CTR CAMBIO": 8312998.79,
            "INSS": 7725531.70,
            "COMEXIM - OURO FINO": 6341123.43,
        }

        total_ia = sum(fornecedores_ia.values())
        print(f"Total (top 5): R$ {total_ia:,.2f}")

        for i, (nome, valor) in enumerate(fornecedores_ia.items(), 1):
            print(f"{i}. {nome}: R$ {valor:,.2f}")

        print("\n3. TESTANDO DIFERENTES CENÁRIOS:")
        print("=" * 80)

        # Busca todas as contas a pagar
        result_all = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)

        # Data de hoje
        hoje = datetime.now().strftime('%Y%m%d')
        print(f"\nHoje: {hoje}")

        # Testa diferentes cenários
        cenarios = [
            ("Todas as contas (sem filtro)", None),
            (f"Desde hoje ({hoje})", hoje),
            ("Desde 27/01/2026", "20260127"),
            ("Janeiro 2026 (desde 01/01)", "20260101"),
        ]

        for descricao, data_filtro in cenarios:
            print(f"\n{'-' * 80}")
            print(f"CENÁRIO: {descricao}")
            print("-" * 80)

            if data_filtro:
                result = [r for r in result_all if r.get("vencimento", "") >= data_filtro]
            else:
                result = result_all

            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            for r in result:
                fornecedor = r.get("fornecedor", "").strip() or "SEM FORNECEDOR"
                valor = r.get("valor", 0)

                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                por_fornecedor[fornecedor]["valor"] += valor
                por_fornecedor[fornecedor]["quantidade"] += 1

            # Top 5
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            print(f"Total de títulos: {len(result)}")
            print(f"\nTop 5 fornecedores:")

            matches = 0
            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:5], 1):
                nome_curto = fornecedor[:40]
                print(f"{i}. {nome_curto:40} R$ {dados['valor']:>15,.2f}")

                # Verifica se bate com a IA
                for nome_ia, valor_ia in fornecedores_ia.items():
                    if nome_ia.upper() in fornecedor.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        if diferenca < 1:
                            matches += 1

            if matches == len(fornecedores_ia):
                print(f"\n[OK] TODOS OS 5 FORNECEDORES BATEM! Este é o cenário correto!")
            else:
                print(f"\nMatches: {matches}/{len(fornecedores_ia)}")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_validacao()
