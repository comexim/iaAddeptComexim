"""
Simula exatamente o que o agente SQL retorna para a IA sobre vendas jan 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions

def test_vendas_aggregation():
    """Simula chamada do agente para vendas janeiro 2026"""
    print("=" * 80)
    print("SIMULACAO DO AGENTE SQL - 'vendas janeiro 2026'")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros SQL\n")

        # Cria user mock com todas as permissões
        user = UserPermissions(
            telefone="5554999999999",
            nome="Test User",
            email="test@example.com",
            direitos=["Vendas", "Compras", "Estoque", "Orçamento", "Financeiro"]
        )

        # Cria instância do SQLTools para usar o _format_results
        sql_tools = SQLTools(user)

        # Chama _format_results que decide se agrega ou não
        print("3. Chamando _format_results (simula o que a IA recebe)...")
        formatted_response = sql_tools._format_results(results, "IA_Vendas", client_filter=None)

        # Salva resposta em arquivo
        with open("vendas_agent_response.txt", "w", encoding="utf-8") as f:
            f.write(formatted_response)

        print("[OK] Resposta salva em 'vendas_agent_response.txt'\n")

        # Verifica se foi agregado
        if "AGREGADOS POR CLIENTE" in formatted_response:
            print("4. AGREGACAO DETECTADA!")
            print("-" * 80)

            # Extrai informação sobre NESTLE ARARAS do JSON
            import json
            import re

            # Procura pelo JSON no formatted_response
            json_match = re.search(r'Dados agregados:\n(\[.*?\])', formatted_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                aggregated = json.loads(json_str)

                # Busca NESTLE ARARAS
                nestle = None
                for cliente in aggregated:
                    if "NESTLE ARARAS" in cliente.get("cliente", "").upper():
                        nestle = cliente
                        break

                if nestle:
                    print(f"\nNESTLE ARARAS encontrado nos dados agregados:")
                    print(f"  Cliente: {nestle.get('cliente')}")
                    print(f"  Diferencial Medio: {nestle.get('diferencial_medio')}")
                    print(f"  Total Contratos: {nestle.get('total_contratos')}")
                    print(f"  Total Sacas: {nestle.get('total_sacas')}")
                    print(f"  Total Valor: R$ {nestle.get('total_valor'):,.2f}")

                    print(f"\n5. COMPARACAO:")
                    print("-" * 80)
                    print(f"Python calculou (no JSON): {nestle.get('diferencial_medio')}")
                    print(f"IA deveria usar: {nestle.get('diferencial_medio')}")
                    print(f"IA esta dizendo: 13.0")
                    print(f"ERRO: IA nao esta usando o valor pre-calculado!")
                else:
                    print("\n[AVISO] NESTLE ARARAS nao encontrado nos dados agregados")
            else:
                print("\n[AVISO] Nao conseguiu extrair JSON da resposta")

        else:
            print("4. AGREGACAO NAO DETECTADA!")
            print("-" * 80)
            print(f"Total de registros enviados para IA: {len(results)}")
            print(f"Threshold para agregacao: >50")
            print(f"Deveria agregar: {'SIM' if len(results) > 50 else 'NAO'}")

        print("\n" + "=" * 80)
        print("[OK] SIMULACAO CONCLUIDA")
        print("=" * 80)
        print("\nVeja o arquivo 'vendas_agent_response.txt' para detalhes completos")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_vendas_aggregation()
