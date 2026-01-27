"""
Testa a tool de pesquisa de contas a pagar
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_contas_a_pagar():
    """Testa pesquisa de contas a pagar"""
    print("=" * 80)
    print("TESTE - Tool pesquisa_contas_a_pagar")
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

        # Teste 1: Contas a pagar desde 12/12/2025
        print("2. Teste 1: Contas a pagar desde 12/12/2025")
        sql_tools.user_query = "Quais contas vou pagar desde 12/12/2025?"
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento="12/12/2025")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres")
            print(f"Primeiros 500 chars: {result[:500]}\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 2: Todas as contas a pagar (sem filtro)
        print("3. Teste 2: Todas as contas a pagar (sem filtro de data)")
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento=None)

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 3: Contas a pagar este mes
        print("4. Teste 3: Contas a pagar este mes")
        sql_tools.user_query = "Quais contas vou pagar este mes?"
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento="este mes")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 4: Contas a pagar proximos 7 dias
        print("5. Teste 4: Contas a pagar proximos 7 dias")
        sql_tools.user_query = "Quais contas vou pagar nos proximos 7 dias?"
        result = sql_tools._pesquisa_contas_a_pagar(data_vencimento="proximos 7 dias")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        print("=" * 80)
        print("[OK] TESTES CONCLUIDOS")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_contas_a_pagar()
