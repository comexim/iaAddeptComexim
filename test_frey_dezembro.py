"""
Testa: contratos FREY A/S em dezembro 2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.utils.date_parser import date_parser
from decimal import Decimal

def test_frey():
    """Testa FREY A/S em dezembro 2025"""
    print("=" * 80)
    print("TESTE - FREY A/S em dezembro 2025")
    print("=" * 80)

    try:
        print("\n1. Testando extração do nome do cliente")
        print("-" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "quantos contratos de venda tivemos para o cliente FREY A/S em dezembro de 2025?"

        client_name = sql_tools._extract_client_name(sql_tools.user_query)
        print(f"Cliente extraído: '{client_name}'")

        if client_name:
            if "/" in client_name:
                print("[OK] Barra '/' foi capturada")
            else:
                print("[X] PROBLEMA: Barra '/' NÃO foi capturada!")
                print("    Isso vai fazer o filtro falhar")
        else:
            print("[X] ERRO: Nenhum cliente foi extraído!")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Testando date_parser com 'dezembro 2025'")
        print("-" * 80)
        parsed = date_parser.parse_natural_date("dezembro 2025")
        print(f"Resultado: {parsed}")

        if parsed and "mes_embarque" in parsed:
            print(f"  mes_embarque: {parsed['mes_embarque']}")

        print("\n4. Buscando contratos de dezembro 2025")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas", filters={"mesEmbarque": "2025/12"})

        if result:
            print(f"Total de contratos em dezembro 2025: {len(result)}")

            # Filtra por FREY
            frey_results = [r for r in result if "FREY" in str(r.get("cliente", "")).upper()]
            print(f"\nContratos com 'FREY' no nome: {len(frey_results)}")

            if frey_results:
                print("\nClientes FREY encontrados:")
                clientes_unicos = set()
                for r in frey_results:
                    cliente = r.get("cliente", "").strip()
                    if cliente:
                        clientes_unicos.add(cliente)

                for cliente in sorted(clientes_unicos):
                    contratos_cliente = [r for r in frey_results if r.get("cliente", "").strip() == cliente]
                    print(f"  - {cliente}: {len(contratos_cliente)} contratos")

                    # Mostra alguns contratos de exemplo
                    for i, c in enumerate(contratos_cliente[:3], 1):
                        contrato = c.get("contrato", "")
                        valor = c.get("valor", 0)
                        if isinstance(valor, Decimal):
                            valor = float(valor)
                        print(f"    {i}. {contrato} - R$ {valor:,.2f}")

            # Testa com filtro exato "FREY A/S"
            print("\n" + "-" * 80)
            print("Testando filtro exato 'FREY A/S':")
            frey_as_results = [r for r in result if "FREY A/S" in str(r.get("cliente", "")).upper()]
            print(f"Contratos com 'FREY A/S' (exato): {len(frey_as_results)}")

            # Testa com filtro parcial "FREY A" (sem barra)
            print("\nTestando filtro parcial 'FREY A' (sem barra):")
            frey_a_results = [r for r in result if "FREY A" in str(r.get("cliente", "")).upper()]
            print(f"Contratos com 'FREY A' (sem /S): {len(frey_a_results)}")

            if len(frey_a_results) > len(frey_as_results):
                print("\n[!] PROBLEMA: Filtro sem barra retorna MAIS resultados!")
                print("    Isso significa que há outros clientes com 'FREY A' no nome")
                print("    Exemplos:")
                clientes_extras = set()
                for r in frey_a_results:
                    cliente = r.get("cliente", "").strip()
                    if "FREY A/S" not in cliente.upper():
                        clientes_extras.add(cliente)
                for cliente in sorted(clientes_extras)[:5]:
                    print(f"      - {cliente}")

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
    test_frey()
