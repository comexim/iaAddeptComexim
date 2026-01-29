"""
Testa despesas do contrato 400/25A
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_despesa_400_25A():
    """Testa despesas do contrato 400/25A"""
    print("=" * 80)
    print("TESTE - Despesas do contrato 400/25A")
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

        print("2. Testando: 'Quais as despesas do contrato 400/25A?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais as despesas do contrato 400/25A?"

        result = sql_tools._pesquisa_despesa_venda(contrato="400/25A")

        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(result)
        print("=" * 80)

        # Verifica se é realmente vazio
        if "nenhuma despesa" in result.lower() or "não foram encontradas" in result.lower():
            print("\n[OK] Confirmado: não há despesas para o contrato 400/25A")
        elif result and len(result) > 50:
            print("\n[AVISO] Parece que há despesas! A IA pode ter errado.")

        # Testa diretamente no banco
        print("\n\n3. VERIFICAÇÃO DIRETA NO BANCO:")
        print("-" * 80)
        result_direto = sql_client.execute_function("dbo.IA_DespesaVenda", filters={"contrato": "400/25A"})

        if result_direto and len(result_direto) > 0:
            print(f"[ERRO] Banco retornou {len(result_direto)} despesas!")
            print("\nPrimeiras 3 despesas:")
            for i, desp in enumerate(result_direto[:3], 1):
                print(f"{i}. {desp.get('despesa')}: R$ {desp.get('despesaRea', 0)}")
        else:
            print("[OK] Banco também não retornou despesas para 400/25A")
            print("-> Contrato não existe ou não tem despesas cadastradas")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_despesa_400_25A()
