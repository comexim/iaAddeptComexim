"""
Testa query sobre contratos da primeira quinzena de janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_primeira_quinzena():
    """Testa query sobre primeira quinzena"""
    print("=" * 80)
    print("TESTE - CONTRATOS DA PRIMEIRA QUINZENA DE JANEIRO 2026")
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

        # Salva resultado
        with open("test_primeira_quinzena_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Resultado salvo em: test_primeira_quinzena_result.txt\n")

        # Converte resultado para JSON
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

        print(f"3. ANALISE DO RESULTADO:")
        print("-" * 80)
        print(f"Total de clientes retornados: {len(data)}\n")

        if data and len(data) > 0:
            # Conta total de contratos
            total_contratos = sum(c.get("total_contratos", 0) for c in data)
            print(f"Total de contratos: {total_contratos}\n")

            # Verifica se tem lista de contratos
            tem_lista_contratos = any("contratos" in c and c["contratos"] for c in data)

            print("4. PROBLEMA DETECTADO:")
            print("-" * 80)

            if not tem_lista_contratos:
                print("[X] A IA retornou apenas CLIENTES agregados")
                print("    A pergunta pede 'Quais CONTRATOS', nao 'Quais CLIENTES'")
                print(f"    Deveria listar os {total_contratos} contratos individuais\n")
            else:
                print("[OK] A resposta tem lista de contratos\n")

                # Mostra alguns exemplos
                print("Primeiros 5 clientes com seus contratos:")
                for i, cliente_data in enumerate(data[:5], 1):
                    contratos = cliente_data.get("contratos", "")
                    print(f"{i}. {cliente_data.get('cliente')}: {contratos}")

                # Conta contratos listados
                total_listados = 0
                for c in data:
                    contratos_str = c.get("contratos", "")
                    if contratos_str:
                        total_listados += len([x.strip() for x in contratos_str.split(',') if x.strip()])

                print(f"\nTotal de contratos listados: {total_listados}")
                print(f"Total de contratos no total_contratos: {total_contratos}")

                if total_listados < total_contratos:
                    print(f"\n[AVISO] Lista incompleta: {total_listados} de {total_contratos}")

            print("\n5. RESPOSTA ESPERADA:")
            print("-" * 80)
            print("A IA deveria responder algo como:")
            print(f"'Na primeira quinzena de janeiro 2026 foram emitidos {total_contratos} contratos:")
            print("1. 400/25A (BERNHARD ROTHFOS GMB)")
            print("2. 400/25B (BERNHARD ROTHFOS GMB)")
            print("3. ...")
            print(f"{total_contratos}. [ultimo contrato]'")
            print("\nOu pelo menos avisar: 'foram emitidos X contratos para Y clientes'")

        else:
            print("Nenhum dado retornado")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_primeira_quinzena()
