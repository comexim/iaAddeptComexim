"""
Testa query sobre ID Protheus de contrato
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_id_protheus():
    """Testa query sobre ID Protheus"""
    print("=" * 80)
    print("TESTE - ID PROTHEUS DO CONTRATO 021/25")
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

        print("2. Query: 'Qual o ID Protheus do contrato 021/25?'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Qual o ID Protheus do contrato 021/25?"

        result = sql_tools._pesquisa_vendas(periodo="janeiro 2026")

        print(f"[OK] Retornou resultado\n")
        print(f"DEBUG - Tipo: {type(result)}")

        # Salva resultado
        with open("test_id_protheus_result.txt", "w", encoding="utf-8") as f:
            f.write(str(result))
        print("Resultado salvo em: test_id_protheus_result.txt\n")

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

        print(f"3. Total de clientes retornados: {len(data)}\n")

        if data and len(data) > 0:
            # Pega as colunas do primeiro resultado
            colunas = list(data[0].keys())
            print(f"Total de colunas disponíveis: {len(colunas)}")

            # Procura colunas relacionadas a contrato
            contrato_cols = [c for c in colunas if 'contrat' in c.lower()]
            print(f"\nColunas relacionadas a contrato:")
            for col in contrato_cols:
                print(f"  - {col}")

            # Procura colunas relacionadas a ID ou Protheus
            id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]

            if id_cols:
                print(f"\n[OK] Colunas com ID/Protheus/RecNo encontradas:")
                for col in id_cols:
                    print(f"  - {col}")
            else:
                print(f"\n[AVISO] Nenhuma coluna com ID/Protheus/RecNo encontrada")

            # Busca por contrato 021/25
            print("\n\n4. PROCURANDO CONTRATO 021/25:")
            print("-" * 80)

            # Verifica se tem campo "contratos"
            encontrado = False
            for cliente_data in data:
                contratos_str = cliente_data.get("contratos", "")
                if contratos_str and "021/25" in contratos_str:
                    print(f"\n[OK] Contrato 021/25 encontrado!")
                    print(f"Cliente: {cliente_data.get('cliente')}")
                    print(f"Contratos: {contratos_str}")

                    if id_cols:
                        print("\nCampos de ID/Protheus disponíveis:")
                        for col in id_cols:
                            val = cliente_data.get(col)
                            print(f"  {col}: {val}")

                    encontrado = True
                    break

            if not encontrado:
                print("\n[X] Contrato 021/25 não encontrado nos dados de janeiro 2026")
                print("\nPrimeiros 10 clientes para referência:")
                for i, c in enumerate(data[:10], 1):
                    contratos = c.get("contratos", "")[:100]
                    print(f"{i}. {c.get('cliente')}: {contratos}...")

            print("\n\n5. ANÁLISE:")
            print("-" * 80)
            if not encontrado:
                print("[OK] Contrato 021/25 NÃO EXISTE em janeiro 2026")
                print("-> A resposta da IA está CORRETA: não conseguiu encontrar")
            elif id_cols:
                print("[OK] Contrato existe E há campos de ID disponíveis")
                print("-> O agente deveria conseguir retornar essa informação")
                print(f"-> Campos disponíveis: {', '.join(id_cols)}")
            else:
                print("[OK] Contrato existe MAS não há campos de ID no banco")
                print("-> A resposta da IA está CORRETA: não há ID Protheus disponível")

        else:
            print("Nenhum dado retornado")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
