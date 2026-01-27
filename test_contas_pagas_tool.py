"""
Testa a tool de pesquisa de contas pagas
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_contas_pagas():
    """Testa pesquisa de contas pagas"""
    print("=" * 80)
    print("TESTE - Tool pesquisa_contas_pagas")
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

        # Teste 1: Contas pagas desde 05/12/2025
        print("2. Teste 1: Contas pagas desde 05/12/2025")
        sql_tools.user_query = "Quais contas foram pagas desde 05/12/2025?"
        result = sql_tools._pesquisa_contas_pagas(data_inicio="05/12/2025")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres")
            print(f"Primeiros 500 chars: {result[:500]}\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 2: Todas as contas pagas (sem filtro)
        print("3. Teste 2: Todas as contas pagas (sem filtro de data)")
        result = sql_tools._pesquisa_contas_pagas(data_inicio=None)

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 3: Contas pagas de dezembro 2025
        print("4. Teste 3: Contas pagas de dezembro 2025")
        sql_tools.user_query = "Quais contas foram pagas em dezembro de 2025?"
        result = sql_tools._pesquisa_contas_pagas(data_inicio="dezembro 2025")

        if result:
            print(f"[OK] Retornou resultado")
            print(f"Tamanho da resposta: {len(result)} caracteres\n")
        else:
            print("[ERRO] Nenhum resultado retornado\n")

        # Teste 4: Contas pagas este mês
        print("5. Teste 4: Contas pagas este mes")
        sql_tools.user_query = "Quais contas foram pagas este mes?"
        result = sql_tools._pesquisa_contas_pagas(data_inicio="este mes")

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
    test_contas_pagas()
