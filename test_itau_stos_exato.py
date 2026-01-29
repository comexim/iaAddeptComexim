"""
Testa exatamente como a IA está chamando
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_tool():
    """Testa com diferentes variações"""
    print("=" * 80)
    print("TESTE - Variações de 'Itaú stos'")
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

        testes = [
            "Itaú stos",
            "ITAU STOS",
            "itau stos",
            "Itaú Santos",
            "STOS"
        ]

        for i, banco_teste in enumerate(testes, 1):
            print(f"\n{i}. Teste: banco='{banco_teste}'")
            print("-" * 80)
            sql_tools.user_query = f"Quanto tenho no {banco_teste}?"
            result = sql_tools._pesquisa_saldo_bancario(banco=banco_teste)
            
            # Mostra primeiras 200 caracteres
            if "Nenhuma conta" in result:
                print(f"[X] {result}")
            else:
                print(f"[OK] Encontrou!")
                # Pega só a parte do total
                linhas = result.split('\n')
                for linha in linhas[:10]:
                    if linha.strip():
                        print(linha)

        print("\n[OK] TESTE CONCLUIDO")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tool()
