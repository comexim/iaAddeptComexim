"""
Debug: encontra o JSON malformado
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_json_malformado():
    """Debug JSON malformado"""
    print("=" * 80)
    print("DEBUG - JSON Malformado")
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

        print("2. Executando tool")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto pagamos em dezembro de 2025?"

        result = sql_tools._pesquisa_contas_pagas(data_inicio="dezembro de 2025")

        print(f"[OK] Tool retornou {len(result)} caracteres\n")

        # Tenta encontrar o JSON
        if "[" in result:
            json_start = result.index("[")
            # Mostra o contexto ao redor do inicio do JSON
            print("Contexto antes do JSON:")
            print("-" * 80)
            print(result[max(0, json_start-100):json_start+200])
            print("-" * 80)

            # Tenta achar onde termina
            tentativas = [100, 500, 1000, 2000, 5000, 10000, -1]
            for tamanho in tentativas:
                try:
                    if tamanho == -1:
                        json_end = result.rindex("]") + 1
                    else:
                        json_end = result.index("]", json_start, json_start + tamanho) + 1

                    json_str = result[json_start:json_end]
                    print(f"\nTentando parsear JSON de tamanho {len(json_str)}")

                    import json
                    data = json.loads(json_str)
                    print(f"[OK] JSON parseado com sucesso! {len(data)} fornecedores")
                    break

                except json.JSONDecodeError as e:
                    print(f"[X] Falha ao parsear (tamanho {tamanho if tamanho > 0 else 'completo'}): {e}")
                    print(f"    Erro na posicao: {e.pos}")
                    if e.pos and e.pos < len(json_str):
                        inicio = max(0, e.pos - 100)
                        fim = min(len(json_str), e.pos + 100)
                        print(f"    Contexto do erro:")
                        print(f"    ...{json_str[inicio:fim]}...")
                except ValueError:
                    continue

            # Salva o resultado completo para analise
            with open("dezembro_resultado_completo.txt", "w", encoding="utf-8") as f:
                f.write(result)
            print(f"\n[INFO] Resultado completo salvo em: dezembro_resultado_completo.txt")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_json_malformado()
