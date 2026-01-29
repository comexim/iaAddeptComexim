"""
Testa query sobre clientes sem código de referência
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_clientes_sem_ref():
    """Testa query sobre clientes sem referência"""
    print("=" * 80)
    print("TESTE - CLIENTES SEM CODIGO DE REFERENCIA EM JANEIRO 2026")
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

        print("2. Query: 'Quais clientes de janeiro 2026 não têm código de referência cadastrado?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais clientes de janeiro 2026 não têm código de referência cadastrado?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")

        with open("test_clientes_sem_ref_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Resultado salvo em: test_clientes_sem_ref_result.txt\n")

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

        # Verifica campos disponíveis
        if data:
            primeiro = data[0]
            print("4. Campos do primeiro cliente:")
            for key in sorted(primeiro.keys()):
                if 'ref' in key.lower() or 'codigo' in key.lower():
                    print(f"  - {key}: {primeiro[key]}")

        # Conta clientes sem referência
        print("\n5. Analisando clientes sem código de referência:")
        clientes_sem_ref = []
        
        for item in data:
            cliente = item.get("cliente", "N/A").strip()
            # Procura campos relacionados a referência
            tem_ref = False
            for key in item.keys():
                if 'ref' in key.lower() and item[key]:
                    tem_ref = True
                    break
            
            if not tem_ref:
                clientes_sem_ref.append(cliente)

        print(f"\nTotal de clientes SEM referência: {len(clientes_sem_ref)}")
        if clientes_sem_ref:
            for i, cliente in enumerate(clientes_sem_ref, 1):
                print(f"{i}. {cliente}")

        print(f"\nIA disse: 3 clientes")
        if len(clientes_sem_ref) == 3:
            print("✓ QUANTIDADE CORRETA!")
        else:
            print(f"✗ QUANTIDADE ERRADA! Correto: {len(clientes_sem_ref)}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_clientes_sem_ref()
