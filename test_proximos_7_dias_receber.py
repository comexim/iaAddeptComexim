"""
Testa: próximos 7 dias em contas a receber
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.utils.date_parser import date_parser

def test_proximos_7_dias():
    """Testa próximos 7 dias"""
    print("=" * 80)
    print("TESTE - Próximos 7 dias (contas a receber)")
    print("=" * 80)

    try:
        print("\n1. Testando date_parser com 'próximos 7 dias'")
        print("-" * 80)
        parsed = date_parser.parse_natural_date("próximos 7 dias")
        print(f"Resultado: {parsed}")

        if parsed:
            print(f"  data_inicio: {parsed.get('data_inicio')}")
            print(f"  data_fim: {parsed.get('data_fim')}")

        print("\n2. Conectando ao banco...")
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
        sql_tools.user_query = "Contas a receber nos próximos 7 dias"

        print("\n3. Executando: pesquisa_contas_a_receber(data_vencimento='próximos 7 dias')")
        print("-" * 80)

        result = sql_tools._pesquisa_contas_a_receber(data_vencimento="próximos 7 dias", cliente=None)

        print("\n4. RESULTADO DA TOOL:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        # Verifica manualmente no banco
        print("\n5. VERIFICACAO MANUAL NO BANCO:")
        print("-" * 80)

        # Hoje é 27/01/2026, próximos 7 dias = 27/01 até 03/02
        data_inicio = "20260127"
        data_fim = "20260203"

        print(f"Hoje: 27/01/2026")
        print(f"Próximos 7 dias: {data_inicio} até {data_fim}")

        result_banco = sql_client.execute_function("dbo.IA_ContasAReceber", filters={"vencimentoReal": data_inicio})

        if result_banco:
            print(f"\nTotal bruto (>= {data_inicio}): {len(result_banco)}")

            # Filtra até data_fim
            result_filtrado = [r for r in result_banco if r.get("vencimentoReal", "") <= data_fim]
            print(f"Total filtrado (<= {data_fim}): {len(result_filtrado)}")

            # Calcula total
            from decimal import Decimal
            total = 0
            for r in result_filtrado:
                valor = r.get("valor", 0)
                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif valor is None:
                    valor = 0
                total += valor

            print(f"\nTotal correto (próximos 7 dias): R$ {total:,.2f}")
            print(f"IA disse: R$ 13.201.816,39")
            print(f"Diferença: R$ {abs(total - 13201816.39):,.2f}")

            # Mostra registros
            print(f"\nRegistros nos próximos 7 dias ({data_inicio} até {data_fim}):")
            for r in result_filtrado[:10]:
                vencimento = r.get("vencimentoReal", "")
                cliente = r.get("cliente", "").strip()
                valor = r.get("valor", 0)
                if isinstance(valor, Decimal):
                    valor = float(valor)
                print(f"  {vencimento} - {cliente[:30]:30} R$ {valor:>12,.2f}")

        print("\n[OK] TESTE CONCLUIDO")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_proximos_7_dias()
