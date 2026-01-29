"""
Testa query sobre contratos que não enviaram amostra em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_amostras_jan2026():
    """Testa query sobre contratos sem amostra enviada"""
    print("=" * 80)
    print("TESTE - CONTRATOS SEM AMOSTRA ENVIADA EM JANEIRO 2026")
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

        print("2. Query: 'Quais contratos de janeiro 2026 ainda não enviaram amostra?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais contratos de janeiro 2026 ainda não enviaram amostra?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")

        with open("test_amostras_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Resultado salvo em: test_amostras_result.txt\n")

        if isinstance(result, str):
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(result)
        else:
            data = result

        print(f"3. Total de clientes: {len(data)}\n")

        total_contratos = 0
        total_com_amostra = 0

        for item in data:
            contratos_cliente = item.get("total_contratos", 0)
            com_amostra = item.get("total_contratos_amostra_enviada", 0)
            total_contratos += contratos_cliente
            total_com_amostra += com_amostra

        total_sem_amostra = total_contratos - total_com_amostra

        print("TOTALIZADORES:")
        print(f"Total de contratos: {total_contratos}")
        print(f"COM amostra: {total_com_amostra}")
        print(f"SEM amostra: {total_sem_amostra}")

        print(f"\nIA disse: 4 contratos")
        if total_sem_amostra == 4:
            print("✓ CORRETO!")
        else:
            print(f"✗ ERRADO! Correto: {total_sem_amostra}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_amostras_jan2026()
