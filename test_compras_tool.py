"""
Testa a tool de pesquisa de compras
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_compras():
    """Testa pesquisa de compras"""
    print("=" * 80)
    print("TESTE - Tool pesquisa_compras")
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

        # Teste 1: Compras desde 05/12/2025
        print("2. Teste 1: Compras desde 05/12/2025")
        sql_tools.user_query = "Quais foram as compras desde 05/12/2025?"
        result = sql_tools._pesquisa_compras(data_inicio="05/12/2025")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres")
            print(f"Primeiros 500 chars: {result[:500]}\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 2: Todas as compras (sem filtro)
        print("3. Teste 2: Todas as compras (sem filtro de data)")
        result = sql_tools._pesquisa_compras(data_inicio=None)

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 3: Compras de dezembro
        print("4. Teste 3: Compras de dezembro 2025")
        sql_tools.user_query = "Quais foram as compras de dezembro 2025?"
        result = sql_tools._pesquisa_compras(data_inicio="dezembro 2025")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        print("=" * 80)
        print("[OK] TESTES CONCLUÍDOS")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_compras()
