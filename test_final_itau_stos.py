"""
Teste final com exatamente o que o usuário perguntou
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_tool():
    """Testa exatamente: 'Quanto tenho no Itaú stos?'"""
    print("=" * 80)
    print("TESTE FINAL - Quanto tenho no Itaú stos?")
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
        sql_tools.user_query = "Quanto tenho no Itaú stos?"

        # Teste 1: Como deveria ser chamado (Itaú stos)
        print("\n2. TESTE CORRETO: banco='Itaú stos'")
        print("-" * 80)
        result1 = sql_tools._pesquisa_saldo_bancario(banco="Itaú stos")
        
        if "Nenhuma conta" in result1:
            print(f"[X] ERRO: {result1}")
        else:
            print("[OK] FUNCIONOU!")
            linhas = result1.split('\n')
            for linha in linhas[:15]:
                if linha.strip():
                    print(linha)

        # Teste 2: Como a IA está chamando errado (Itaú Santos)
        print("\n\n3. TESTE ERRADO (como IA está fazendo): banco='Itaú Santos'")
        print("-" * 80)
        result2 = sql_tools._pesquisa_saldo_bancario(banco="Itaú Santos")
        
        if "Nenhuma conta" in result2:
            print(f"[X] ERRO (esperado): {result2}")
        else:
            print("[OK] Funcionou (inesperado)")

        print("\n[OK] TESTE CONCLUIDO")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tool()
