"""
Testa tool de saldo bancário
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_tool():
    """Testa tool de saldo bancário"""
    print("=" * 80)
    print("TESTE - Tool pesquisa_saldo_bancario")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
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
        sql_tools.user_query = "Qual o saldo bancário?"

        print("\n2. Executando: pesquisa_saldo_bancario()")
        print("-" * 80)

        result = sql_tools._pesquisa_saldo_bancario()

        print("\n3. RESULTADO DA TOOL:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        print("\n[OK] TESTE CONCLUIDO")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tool()
