"""
Testa query sobre intersecção: embarcados E baixados
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_embarcados_e_baixados():
    """Testa query com AMBOS embarcados E baixados"""
    print("=" * 80)
    print("TESTE - EMBARCADOS E BAIXADOS EM JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Cria objeto fake de user
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Query: 'Dos contratos que já embarcaram em janeiro 2026, quantos já foram baixados no contas a receber?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Dos contratos que já embarcaram em janeiro 2026, quantos já foram baixados no contas a receber?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Tamanho: {len(result) if result else 0}")

        # Verifica se é a resposta otimizada
        if isinstance(result, str):
            if "RESPOSTA DIRETA" in result:
                print("\n[OK] OTIMIZAÇÃO FOI ATIVADA!")
                print("-" * 80)
                # Salva resultado em arquivo para evitar problemas de encoding
                with open("test_embarcados_result.txt", "w", encoding="utf-8") as f:
                    f.write(result)
                print("Resultado salvo em: test_embarcados_result.txt")
                print("-" * 80)
            else:
                print("\n[ERRO] OTIMIZAÇÃO NÃO FOI ATIVADA")
                print("Primeiros 500 chars do resultado:")
                print(result[:500])
        else:
            print("\n[ERRO] Resultado não é string, otimização não funcionou")
            print(f"Tipo: {type(result)}")

        print("\n" + "=" * 80)
        print("TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_embarcados_e_baixados()
