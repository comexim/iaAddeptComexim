"""
Debug: Analisa campos valor vs saldo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_debug():
    """Debug valor vs saldo"""
    print("=" * 80)
    print("DEBUG - Contas a Receber Janeiro 2026 (valor vs saldo)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        # Busca janeiro 2026
        result = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": "20260101"})

        if result:
            result_filtrado = [r for r in result if r.get("vencimentoReal", "") <= "20260131"]
            print(f"\nTotal de registros janeiro 2026: {len(result_filtrado)}")

            # Agrega por cliente com AMBOS os campos
            por_cliente = defaultdict(lambda: {"valor": 0, "saldo": 0, "qtd": 0})

            for r in result_filtrado:
                cliente = r.get("cliente", "").strip() or "SEM CLIENTE"
                valor = r.get("valor", 0)
                saldo = r.get("saldo", 0)

                # Converte valor
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

                # Converte saldo
                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0
                elif not isinstance(saldo, (int, float)):
                    saldo = 0

                por_cliente[cliente]["valor"] += valor
                por_cliente[cliente]["saldo"] += saldo
                por_cliente[cliente]["qtd"] += 1

            print("\n" + "=" * 80)
            print("COMPARAÇÃO: VALOR vs SALDO")
            print("=" * 80)

            total_valor = sum(dados["valor"] for dados in por_cliente.values())
            total_saldo = sum(dados["saldo"] for dados in por_cliente.values())

            print(f"\nTOTAL USANDO VALOR: R$ {total_valor:,.2f}")
            print(f"TOTAL USANDO SALDO: R$ {total_saldo:,.2f}")
            print(f"TOTAL DA IA:        R$ 13,219,599.31")

            diferenca_valor = abs(total_valor - 13219599.31)
            diferenca_saldo = abs(total_saldo - 13219599.31)

            print(f"\nDiferença se usar VALOR: R$ {diferenca_valor:,.2f}")
            print(f"Diferença se usar SALDO: R$ {diferenca_saldo:,.2f}")

            if diferenca_saldo < diferenca_valor:
                print("\n[INFO] IA está usando SALDO!")
                campo_correto = "saldo"
            else:
                print("\n[INFO] IA está usando VALOR!")
                campo_correto = "valor"

            print("\n" + "=" * 80)
            print(f"TOP 5 CLIENTES (por {campo_correto.upper()}):")
            print("=" * 80)

            clientes_ordenados = sorted(por_cliente.items(),
                                       key=lambda x: abs(x[1][campo_correto]),
                                       reverse=True)

            clientes_ia = {
                "NESTLE ARARAS": 1544734.89,
                "KRAFT": 12997.60,
                "NESTRADE S.A.": 173098.15,
                "MATIAS RUIZ & CIA.SA": 214720.00,
                "NEUMANN GRUPPE USA I": 647695.43,
            }

            matches = 0
            for i, (cliente, dados) in enumerate(clientes_ordenados[:10], 1):
                print(f"\n{i}. {cliente[:50]}")
                print(f"   Valor: R$ {dados['valor']:>15,.2f}")
                print(f"   Saldo: R$ {dados['saldo']:>15,.2f}")
                print(f"   Títulos: {dados['qtd']}")

                # Verifica match com IA
                for nome_ia, valor_ia in clientes_ia.items():
                    if nome_ia.upper() in cliente.upper():
                        diferenca_valor_campo = abs(dados['valor'] - valor_ia)
                        diferenca_saldo_campo = abs(dados['saldo'] - valor_ia)

                        if diferenca_saldo_campo < diferenca_valor_campo:
                            if diferenca_saldo_campo < 1:
                                print(f"   [OK] IA: R$ {valor_ia:,.2f} (SALDO - EXATO!)")
                                matches += 1
                            else:
                                print(f"   [~] IA: R$ {valor_ia:,.2f} (SALDO - Dif: R$ {diferenca_saldo_campo:,.2f})")
                        else:
                            if diferenca_valor_campo < 1:
                                print(f"   [OK] IA: R$ {valor_ia:,.2f} (VALOR - EXATO!)")
                                matches += 1
                            else:
                                print(f"   [~] IA: R$ {valor_ia:,.2f} (VALOR - Dif: R$ {diferenca_valor_campo:,.2f})")
                        break

            print("\n" + "=" * 80)
            print(f"[INFO] {matches}/5 clientes validados")
            print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug()
