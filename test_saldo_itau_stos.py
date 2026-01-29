"""
Testa saldo do Itaú STOS com filtro correto
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_tool():
    """Testa tool com filtro de banco"""
    print("=" * 80)
    print("TESTE - Saldo Itaú (STOS, SANTOS, e só ITAU)")
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

        # Teste 1: ITAU STOS
        print("\n2. Teste 1: pesquisa_saldo_bancario(banco='ITAU STOS')")
        print("-" * 80)
        sql_tools.user_query = "Quanto tenho no Itaú STOS?"
        result1 = sql_tools._pesquisa_saldo_bancario(banco="ITAU STOS")
        print(result1[:500])

        # Teste 2: ITAU (pega todas as contas Itaú)
        print("\n\n3. Teste 2: pesquisa_saldo_bancario(banco='ITAU')")
        print("-" * 80)
        sql_tools.user_query = "Quanto tenho no Itaú?"
        result2 = sql_tools._pesquisa_saldo_bancario(banco="ITAU")
        print(result2[:800])

        print("\n[OK] TESTE CONCLUIDO")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tool()
