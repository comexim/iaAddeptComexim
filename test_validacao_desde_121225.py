"""
Validação: Contas a pagar desde 12/12/2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida se existem contas desde 12/12/2025"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar desde 12/12/2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Buscando contas desde 12/12/2025 (20251212):")
        print("-" * 80)

        # Busca com filtro
        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": "20251212"})

        if not result:
            print("[X] NENHUM RESULTADO RETORNADO!")
            print("\nTestando sem filtro para ver se a função está funcionando...")
            result_all = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)
            print(f"Total sem filtro: {len(result_all) if result_all else 0}")

            if result_all:
                # Filtra manualmente
                desde_121225 = [r for r in result_all if r.get("vencimento", "") >= "20251212"]
                print(f"Total >= 20251212 (filtro manual): {len(desde_121225)}")

                if desde_121225:
                    # Agrega por fornecedor
                    por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0})
                    total_valor = 0

                    for r in desde_121225:
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

                    print(f"\nValor total a pagar (desde 12/12/2025): R$ {total_valor:,.2f}")

                    # Top 10
                    print("\n" + "=" * 80)
                    print("TOP 10 FORNECEDORES (DESDE 12/12/2025):")
                    print("=" * 80)

                    fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

                    for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
                        nome_curto = fornecedor[:40]
                        print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:3} títulos)")
        else:
            print(f"[OK] Retornou {len(result)} registros")

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

            print(f"\nValor total a pagar (desde 12/12/2025): R$ {total_valor:,.2f}")

            # Top 10
            print("\n" + "=" * 80)
            print("TOP 10 FORNECEDORES (DESDE 12/12/2025):")
            print("=" * 80)

            fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
                nome_curto = fornecedor[:40]
                print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:3} títulos)")

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
