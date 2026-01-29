"""
Testa filtro de cliente FREY A/S
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal

def test_filtro():
    """Testa filtro de cliente"""
    print("=" * 80)
    print("TESTE - Filtro de cliente FREY A/S")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Buscando contratos de dezembro 2025")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas", filters={"mesEmbarque": "2025/12"})

        if not result:
            print("[ERRO] Nenhum contrato encontrado")
            return

        print(f"Total de contratos em dezembro 2025: {len(result)}")

        print("\n3. Testando _filter_by_client")
        print("-" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        # Testa com "frey a/s" (lowercase, com barra)
        filtered = sql_tools._filter_by_client(result, "frey a/s")
        print(f"\nFiltro 'frey a/s': {len(filtered)} contratos encontrados")

        if filtered:
            print("Clientes encontrados:")
            for r in filtered:
                cliente = r.get("cliente", "")
                contrato = r.get("contrato", "")
                print(f"  - {cliente} (contrato {contrato})")
        else:
            print("[X] NENHUM contrato encontrado!")
            print("\n" + "-" * 80)
            print("Debug: Vendo o que tem no banco com 'FREY'")
            for r in result:
                cliente = r.get("cliente", "").upper()
                if "FREY" in cliente:
                    contrato = r.get("contrato", "")
                    print(f"  Banco tem: '{r.get('cliente', '')}' (contrato {contrato})")

        # Testa também com maiúsculas
        print("\n" + "-" * 80)
        filtered2 = sql_tools._filter_by_client(result, "FREY A/S")
        print(f"Filtro 'FREY A/S' (maiúsculas): {len(filtered2)} contratos encontrados")

        # Testa sem barra
        print("\n" + "-" * 80)
        filtered3 = sql_tools._filter_by_client(result, "FREY A")
        print(f"Filtro 'FREY A' (sem barra): {len(filtered3)} contratos encontrados")

        # Testa apenas "FREY"
        print("\n" + "-" * 80)
        filtered4 = sql_tools._filter_by_client(result, "FREY")
        print(f"Filtro 'FREY' (apenas): {len(filtered4)} contratos encontrados")

        print("\n4. Testando ferramenta completa")
        print("=" * 80)

        sql_tools.user_query = "quantos contratos de venda tivemos para o cliente FREY A/S em dezembro de 2025?"
        response = sql_tools._pesquisa_vendas(periodo="dezembro 2025")

        print("\nResposta da tool:")
        print(response[:1000])

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
    test_filtro()
