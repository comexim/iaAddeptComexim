"""
Simula exatamente o que a IA faz ao processar a pergunta
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
import json

def test_simula_ia():
    """Simula IA processando a pergunta"""
    print("=" * 80)
    print("SIMULACAO - IA processando 'Quanto pagamos em dezembro de 2025?'")
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

        print("2. Criando SQLTools e definindo user_query")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto pagamos em dezembro de 2025?"

        print("3. Chamando tool pesquisa_contas_pagas com data_inicio='dezembro de 2025'")

        try:
            result = sql_tools._pesquisa_contas_pagas(data_inicio="dezembro de 2025")

            print(f"[OK] Tool executou sem erros")
            print(f"Tamanho do resultado: {len(result)} caracteres")

            # Verifica se é JSON
            if result.startswith("Resultados da consulta"):
                print("\n[OK] Formato correto (agregado)")

                # Tenta extrair informacoes
                if "Total de registros SQL:" in result:
                    import re
                    match = re.search(r'Total de registros SQL: (\d+)', result)
                    if match:
                        total = match.group(1)
                        print(f"Total de registros: {total}")

                if "Valor total pago:" in result:
                    import re
                    match = re.search(r'Valor total pago: R\$ ([-\d,\.]+)', result)
                    if match:
                        valor = match.group(1)
                        print(f"Valor total: R$ {valor}")

                # Mostra inicio da lista de fornecedores
                if "[" in result:
                    json_start = result.index("[")
                    json_end = result.index("]", json_start) + 1
                    json_str = result[json_start:json_end]

                    try:
                        data = json.loads(json_str)
                        print(f"\nTotal de fornecedores no JSON: {len(data)}")
                        print("\nTop 5 fornecedores:")
                        for i, forn in enumerate(data[:5], 1):
                            nome = forn.get("fornecedor", "N/A")
                            valor = forn.get("valor_total", 0)
                            print(f"  {i}. {nome[:50]}: R$ {abs(valor):,.2f}")
                    except json.JSONDecodeError as e:
                        print(f"[ERRO] Falha ao parsear JSON: {e}")

            else:
                print("[AVISO] Formato inesperado")
                print(f"Primeiros 500 chars: {result[:500]}")

            print("\n[OK] Teste concluido com sucesso")

        except Exception as e:
            print(f"[ERRO] Excecao ao executar tool: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"\n[ERRO GERAL] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_simula_ia()
