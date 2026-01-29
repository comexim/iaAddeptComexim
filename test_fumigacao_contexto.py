"""
Testa agregação de despesas de fumigação COM CONTEXTO
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_fumigacao_contexto():
    """Testa fumigação com contexto de múltiplas perguntas"""
    print("=" * 80)
    print("TESTE - Fumigação com contexto (múltiplas perguntas)")
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

        # Simula o contexto que aconteceu no servidor
        print("2. Simulando contexto: 'Quanto gastei com desembaraço em todos os contratos? Quanto gastei com fumigação?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto gastei com desembaraço em todos os contratos? Quanto gastei com fumigação?"

        result = sql_tools._pesquisa_despesa_venda(contrato=None)

        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        print()
        print("DEVE detectar 'fumigação' (última pergunta), NÃO 'desembaraço'")

        if "fumigacao" in result.lower():
            print("[OK] Detectou fumigação corretamente!")
        else:
            print("[ERRO] NÃO detectou fumigação!")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_fumigacao_contexto()
