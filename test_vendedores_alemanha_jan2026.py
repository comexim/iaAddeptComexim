"""
Testa query sobre vendedores que venderam para Alemanha em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_vendedores_alemanha_jan2026():
    """Testa query sobre vendedores para Alemanha"""
    print("=" * 80)
    print("TESTE - VENDEDORES QUE VENDERAM PARA ALEMANHA EM JANEIRO 2026")
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

        print("2. Query: 'Quais vendedores venderam para a Alemanha em janeiro 2026?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais vendedores venderam para a Alemanha em janeiro 2026?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Tamanho: {len(result) if isinstance(result, list) else len(str(result))}")

        # Verifica se é lista ou string JSON
        if isinstance(result, str):
            print(f"DEBUG - Primeiros 500 chars: {result[:500]}\n")
            # Salva resultado completo em arquivo
            with open("test_vendedores_alemanha_result.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print("Resultado completo salvo em: test_vendedores_alemanha_result.txt\n")

            if not result or result.strip() == "":
                print("[ERRO] Resultado vazio!")
                return
            if result.startswith("PRECISA_"):
                print(f"[ERRO] {result}")
                return

            # Extrai JSON da resposta formatada
            if "[" in result:
                json_start = result.index("[")
                json_end = result.rindex("]") + 1
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
            else:
                data = json.loads(result)
        else:
            data = result

        print(f"3. Total de registros retornados: {len(data)}\n")

        # Verifica primeiro registro
        print("4. VERIFICANDO CAMPOS NO PRIMEIRO REGISTRO:")
        print("-" * 80)

        if data:
            primeiro = data[0]
            print(f"\nPrimeiro registro:")
            for key in sorted(primeiro.keys()):
                value = primeiro[key]
                if isinstance(value, (list, str)) and len(str(value)) > 100:
                    print(f"  - {key}: {str(value)[:100]}...")
                else:
                    print(f"  - {key}: {value}")

        # Coleta todos os vendedores únicos que venderam para Alemanha
        print("\n\n5. COLETANDO VENDEDORES QUE VENDERAM PARA ALEMANHA:")
        print("-" * 80)

        vendedores_alemanha = set()
        for item in data:
            paises = item.get("paises", [])
            vendedores = item.get("vendedores", [])

            # Se vendeu para Alemanha
            if "ALEMANHA" in [p.upper().strip() for p in paises]:
                for vendedor in vendedores:
                    vendedores_alemanha.add(vendedor.strip())

        if vendedores_alemanha:
            print(f"\nTotal de vendedores únicos: {len(vendedores_alemanha)}\n")
            print("Lista de vendedores:")
            for i, vendedor in enumerate(sorted(vendedores_alemanha), 1):
                print(f"{i}. {vendedor}")
        else:
            print("\n[AVISO] Nenhum vendedor encontrado para Alemanha")
            print("\nPaíses encontrados nos dados:")
            todos_paises = set()
            for item in data:
                paises = item.get("paises", [])
                for pais in paises:
                    todos_paises.add(pais.strip())
            for pais in sorted(todos_paises):
                print(f"  - {pais}")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_vendedores_alemanha_jan2026()
