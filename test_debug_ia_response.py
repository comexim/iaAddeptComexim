"""
Debug: tenta reproduzir a resposta da IA
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_debug_ia():
    """Tenta reproduzir exatamente o que a IA fez"""
    print("=" * 80)
    print("DEBUG - Tentando reproduzir resposta da IA")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        # Testa diferentes cenários
        cenarios = [
            ("Sem filtro (todas as contas)", None),
            ("Desde 01/01/2026", {"vencimento": "20260101"}),
            ("Desde 27/01/2026 (hoje)", {"vencimento": "20260127"}),
            ("Desde 28/01/2026", {"vencimento": "20260128"}),
        ]

        for descricao, filters in cenarios:
            print(f"\n{'=' * 80}")
            print(f"CENÁRIO: {descricao}")
            print("=" * 80)

            result = sql_client.execute_function("dbo.IA_ContasAPagar", filters=filters)

            if not result:
                print("[ERRO] Nenhum resultado")
                continue

            print(f"Total de registros: {len(result)}")

            # Agrega por fornecedor
            por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})

            total_valor = 0
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
                total_valor += valor

            print(f"Valor total: R$ {total_valor:,.2f}")

            # Top 5
            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            print("\nTop 5 fornecedores:")
            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:5], 1):
                nome_curto = fornecedor[:40]
                print(f"{i}. {nome_curto:40} R$ {dados['valor']:>15,.2f}")

            # Verifica se bate com a resposta da IA
            print("\n" + "-" * 80)
            print("COMPARAÇÃO COM RESPOSTA DA IA:")
            print("-" * 80)

            valor_ia = 128781164.62
            diferenca = abs(total_valor - valor_ia)

            if diferenca < 1:
                print(f"[OK] MATCH! Total bate: R$ {total_valor:,.2f}")
            else:
                print(f"[X] Diferenca: R$ {diferenca:,.2f} (IA disse R$ {valor_ia:,.2f}, aqui tem R$ {total_valor:,.2f})")

            # Verifica fornecedores
            fornecedores_ia = {
                "FOLHA": 51846684.97,
                "COOP. TRES PONTAS": 19567999.98,
                "JUROS CTR CAMBIO": 7163396.49,
            }

            matches = 0
            for nome_ia, valor_ia in fornecedores_ia.items():
                for fornecedor, dados in por_fornecedor.items():
                    if nome_ia.upper() in fornecedor.upper():
                        if abs(dados["valor"] - valor_ia) < 1:
                            matches += 1
                            print(f"[OK] {nome_ia}: R$ {dados['valor']:,.2f} (match!)")
                        else:
                            print(f"[X] {nome_ia}: IA disse R$ {valor_ia:,.2f}, aqui R$ {dados['valor']:,.2f}")
                        break

            print(f"\nTotal de matches: {matches}/3")

        print("\n" + "=" * 80)
        print("[OK] DEBUG CONCLUÍDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug_ia()
