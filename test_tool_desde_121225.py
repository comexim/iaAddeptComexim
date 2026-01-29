"""
Testa a tool com 'desde 12/12/2025'
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.utils.date_parser import date_parser

def test_tool():
    """Testa tool com desde 12/12/2025"""
    print("=" * 80)
    print("TESTE - Tool com 'desde 12/12/2025'")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        # Testa o date_parser primeiro
        print("2. Testando date_parser:")
        print("-" * 80)

        testes = [
            "12/12/2025",
            "desde 12/12/2025",
            "20251212"
        ]

        for texto in testes:
            parsed = date_parser.parse_natural_date(texto)
            print(f"Texto: '{texto}'")
            print(f"  Resultado: {parsed}")
            print()

        # Agora testa a tool
        print("3. Testando tool:")
        print("-" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto tenho a pagar desde 12/12/2025?"

        print("\nChamando: _pesquisa_contas_a_pagar(data_vencimento='desde 12/12/2025')")
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento="desde 12/12/2025")

        print("\nRESULTADO DA TOOL:")
        print("=" * 80)
        if "Nenhuma conta" in result:
            print("[X] ERRO: Tool retornou 'Nenhuma conta'")
            print(result[:500])
        else:
            print("[OK] Tool retornou dados")
            print(result[:1000] + "...")
        print("=" * 80)

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
    test_tool()
