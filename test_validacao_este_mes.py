"""
Validação: Recebimentos deste mês
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.utils.date_parser import date_parser
from decimal import Decimal

def test_validacao():
    """Valida recebimentos deste mês"""
    print("=" * 80)
    print("VALIDACAO - Recebimentos deste mês")
    print("=" * 80)

    try:
        print("\n1. Testando date_parser com 'deste mês'")
        print("-" * 80)
        parsed = date_parser.parse_natural_date("deste mês")
        print(f"Resultado: {parsed}")

        if parsed:
            print(f"  data_inicio: {parsed.get('data_inicio')}")
            print(f"  data_fim: {parsed.get('data_fim')}")
            print(f"  mes_embarque: {parsed.get('mes_embarque')}")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total: R$ 795.710,81")
        print("1. NEUMANN GRUPPE USA I: R$ 647.695,43")
        print("2. BIJDENDIJK: R$ 148.015,38")

        print("\n3. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Recebimentos deste mês"

        print("\n4. Executando: pesquisa_contas_a_receber(data_vencimento='deste mês')")
        print("-" * 80)

        result = sql_tools._pesquisa_contas_a_receber(data_vencimento="deste mês", cliente=None)

        print("\n5. RESULTADO DA TOOL:")
        print("=" * 80)
        print(result[:2000])
        print("=" * 80)

        print("\n6. VERIFICACAO MANUAL NO BANCO:")
        print("-" * 80)

        data_inicio = "20260101"
        data_fim = "20260131"

        print(f"Este mês (janeiro 2026): {data_inicio} até {data_fim}")

        result_banco = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": data_inicio})

        if result_banco:
            print(f"\nTotal bruto (>= {data_inicio}): {len(result_banco)}")

            result_filtrado = [r for r in result_banco if r.get("vencimentoReal", "") <= data_fim]
            print(f"Total filtrado (<= {data_fim}): {len(result_filtrado)}")

            total = 0
            for r in result_filtrado:
                valor = r.get("valor", 0)
                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif valor is None:
                    valor = 0
                total += valor

            print(f"\nTotal CORRETO (janeiro inteiro): R$ {total:,.2f}")
            print(f"IA disse: R$ 795.710,81")
            print(f"Diferença: R$ {abs(total - 795710.81):,.2f}")

            if abs(total - 795710.81) < 1:
                print("[OK] IA está correta")
            else:
                print(f"[X] IA está INCORRETA - deveria ser R$ {total:,.2f}")

                print("\n" + "-" * 80)
                print("Verificando se pegou apenas até HOJE (27/01):")
                result_ate_hoje = [r for r in result_banco if r.get("vencimentoReal", "") <= "20260127"]
                print(f"Registros até 27/01: {len(result_ate_hoje)}")

                total_ate_hoje = 0
                for r in result_ate_hoje:
                    valor = r.get("valor", 0)
                    if isinstance(valor, Decimal):
                        valor = float(valor)
                    elif valor is None:
                        valor = 0
                    total_ate_hoje += valor

                print(f"Total até hoje: R$ {total_ate_hoje:,.2f}")

                if abs(total_ate_hoje - 795710.81) < 1:
                    print("[!] IA pegou apenas até HOJE, não o mês inteiro!")
                    print("[!] 'Deste mês' deveria incluir TODO o mês, não só até hoje")

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
