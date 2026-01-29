"""
Validação: Contas a Receber - Janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida contas a receber janeiro 2026"""
    print("=" * 80)
    print("VALIDACAO - Contas a Receber Janeiro 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        clientes_ia = {
            "NESTLE ARARAS": 1544734.89,
            "KRAFT": 12997.60,
            "NESTRADE S.A.": 173098.15,
            "MATIAS RUIZ & CIA.SA": 214720.00,
            "NEUMANN GRUPPE USA I": 647695.43,
        }
        total_ia = 13219599.31

        print(f"Total: R$ {total_ia:,.2f}")
        for i, (nome, valor) in enumerate(clientes_ia.items(), 1):
            print(f"{i}. {nome}: R$ {valor:,.2f}")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca desde 01/01/2026
        result = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": "20260101"})
        print(f"Total bruto (>= 01/01/2026): {len(result) if result else 0}")

        if result:
            # Aplica filtro manual até 31/01
            result_filtrado = [r for r in result if r.get("vencimentoReal", "") <= "20260131"]
            print(f"Total filtrado (<= 31/01/2026): {len(result_filtrado)}")

            # Agrega por cliente
            por_cliente = defaultdict(lambda: {"valor": 0, "saldo": 0})

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

            print("\nTop 5 clientes (por valor):")
            clientes_ordenados = sorted(por_cliente.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

            total_banco = sum(dados["valor"] for dados in por_cliente.values())
            print(f"\nTOTAL BANCO: R$ {total_banco:,.2f}")
            print(f"TOTAL IA:    R$ {total_ia:,.2f}")

            diferenca_total = abs(total_banco - total_ia)
            if diferenca_total < 1:
                print(f"[OK] TOTAIS COINCIDEM!")
            else:
                percentual = (diferenca_total / total_ia * 100) if total_ia > 0 else 0
                print(f"[X] Diferença: R$ {diferenca_total:,.2f} ({percentual:.2f}%)")

            print("\n" + "-" * 80)
            matches = 0
            for i, (cliente, dados) in enumerate(clientes_ordenados[:5], 1):
                print(f"{i}. {cliente[:40]:40} R$ {dados['valor']:>15,.2f}")

                # Verifica match com IA
                for nome_ia, valor_ia in clientes_ia.items():
                    if nome_ia.upper() in cliente.upper():
                        diferenca = abs(dados['valor'] - valor_ia)
                        if diferenca < 1:
                            print(f"   [OK] EXATO!")
                            matches += 1
                        else:
                            percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0
                            print(f"   [X] IA: R$ {valor_ia:,.2f}, Dif: R$ {diferenca:,.2f} ({percentual:.1f}%)")
                        break

            print(f"\n{'=' * 80}")
            if diferenca_total < 1 and matches == 5:
                print("[OK] VALIDACAO 100% CORRETA - Total e Top 5 clientes conferem!")
            elif diferenca_total < 1:
                print(f"[OK] Total correto, {matches}/5 clientes validados")
            else:
                print(f"[INFO] {matches}/5 clientes validados, diferença no total")

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
