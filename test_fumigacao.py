"""
Testa agregação de despesas de fumigação
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_fumigacao():
    """Testa agregação de fumigação"""
    print("=" * 80)
    print("TESTE - Fumigação em todos os contratos")
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

        print("2. Testando: 'Quanto gastei com fumigação?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto gastei com fumigação?"

        result = sql_tools._pesquisa_despesa_venda(contrato=None)

        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        # Extrai valores da resposta da IA
        print("\n3. COMPARAÇÃO:")
        print("-" * 80)
        print("Resposta da IA:")
        print("- R$ 1.200.000,00")
        print("- US$ 2.500,00")
        print("- 150 despesas")
        print("- 120 contratos")
        print()
        print("Resultado do banco:")
        print(result)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_fumigacao()
