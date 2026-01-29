"""
Simula o que a IA GPT-4o está vendo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_simula_ia():
    """Simula exatamente o que a IA recebe"""
    print("=" * 80)
    print("SIMULACAO - O QUE A IA GPT-4o ESTA VENDO")
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

        print("2. Query: 'Quais contratos foram emitidos na primeira quinzena de janeiro 2026?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais contratos foram emitidos na primeira quinzena de janeiro 2026?"

        result = sql_tools._pesquisa_vendas(periodo="primeira quinzena de janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("INICIO DO RESULTADO QUE A IA RECEBE:")
        print("=" * 80)
        print(result[:2000])
        print("\n...")
        print(result[-500:])
        print("=" * 80)
        print("FIM DO RESULTADO")
        print("=" * 80)

        print(f"\nTamanho total: {len(result)} caracteres")
        print(f"Numero de linhas: {result.count(chr(10))}")

        if "RESPOSTA DIRETA" in result:
            print("\n[OK] Tem instrucao 'RESPOSTA DIRETA'")
        else:
            print("\n[PROBLEMA] NAO tem instrucao 'RESPOSTA DIRETA'")

        if "1. " in result and "2. " in result and "(" in result:
            print("[OK] Tem formato de lista numerada com clientes")
        else:
            print("[PROBLEMA] Formato diferente do esperado")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_simula_ia()
