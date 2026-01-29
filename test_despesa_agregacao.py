"""
Testa agregação de despesas
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_agregacao():
    """Testa agregação"""
    print("=" * 80)
    print("TESTE - Agregação de despesas")
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

        print("2. Testando agregação: 'Quanto gastei com desembaraço em todos os contratos?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto gastei com desembaraço em todos os contratos?"

        result = sql_tools._pesquisa_despesa_venda(contrato=None)
        
        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(result[:2000] if isinstance(result, str) else result)
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_agregacao()
