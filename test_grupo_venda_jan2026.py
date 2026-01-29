"""
Testa query sobre vendas por grupo em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_grupo_venda_jan2026():
    """Testa query sobre grupo de venda em janeiro"""
    print("=" * 80)
    print("TESTE - VENDAS POR GRUPO EM JANEIRO 2026")
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

        print("2. IA deveria chamar: pesquisa_vendas(periodo='janeiro 2026')")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Qual o valor total de vendas por grupo de venda em janeiro 2026?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")
        print(f"DEBUG - Tamanho: {len(result) if isinstance(result, list) else len(str(result))}")

        # Verifica se é lista ou string JSON
        if isinstance(result, str):
            print(f"DEBUG - Primeiros 500 chars: {result[:500]}\n")

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

        print(f"3. Total de clientes retornados: {len(data)}\n")

        # Verifica campos
        print("4. VERIFICANDO CAMPOS NO PRIMEIRO CLIENTE:")
        print("-" * 80)

        if data:
            primeiro = data[0]
            print(f"\nCliente: {primeiro.get('cliente', 'N/A')}")
            print(f"\nCampos disponíveis:")
            for key in sorted(primeiro.keys()):
                value = primeiro[key]
                print(f"  - {key}: {value}")

        # Agrupa por grupo de venda
        print("\n\n5. AGREGANDO POR GRUPO DE VENDA:")
        print("-" * 80)

        por_grupo = {}
        for item in data:
            grupos = item.get("grupos_venda", [])
            valor = item.get("total_valor", 0)
            sacas = item.get("total_sacas", 0)

            if not grupos:
                grupos = ["SEM GRUPO"]

            for grupo in grupos:
                if grupo not in por_grupo:
                    por_grupo[grupo] = {"valor": 0, "sacas": 0, "clientes": 0}
                por_grupo[grupo]["valor"] += valor
                por_grupo[grupo]["sacas"] += sacas
                por_grupo[grupo]["clientes"] += 1

        print(f"\nTotal de grupos encontrados: {len(por_grupo)}\n")

        for i, (grupo, totais) in enumerate(sorted(por_grupo.items(), key=lambda x: x[1]["valor"], reverse=True), 1):
            print(f"{i}. {grupo}:")
            print(f"   Valor: R$ {totais['valor']:,.2f}")
            print(f"   Sacas: {totais['sacas']:,.2f}")
            print(f"   Clientes: {totais['clientes']}")

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
    test_grupo_venda_jan2026()
