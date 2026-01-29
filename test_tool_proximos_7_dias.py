"""
Testa a tool com 'próximos 7 dias' e mostra o resultado completo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_proximos_7_dias():
    """Testa próximos 7 dias"""
    print("=" * 80)
    print("TESTE - Tool com 'proximos 7 dias'")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        print("2. Chamando tool: _pesquisa_contas_a_pagar(data_vencimento='proximos 7 dias')")
        print("-" * 80)

        sql_tools.user_query = "Contas a pagar nos proximos 7 dias"
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento="proximos 7 dias")

        print("\nRESULTADO DA TOOL:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        # Extrai o valor total da resposta
        import re
        match = re.search(r'Valor total a pagar: R\$ ([\d\.,]+)', result)
        if match:
            valor_str = match.group(1).replace(".", "").replace(",", ".")
            valor_tool = float(valor_str)
            print(f"\nValor total reportado pela tool: R$ {valor_tool:,.2f}")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_proximos_7_dias()
