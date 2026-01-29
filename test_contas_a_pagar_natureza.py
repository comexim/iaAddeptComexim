"""
Testa filtro por natureza em contas a pagar
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_natureza():
    """Testa filtro por natureza"""
    print("=" * 80)
    print("TESTE - Filtro por natureza em contas a pagar")
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

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto tenho a pagar de compra de café?"

        # Testa diferentes filtros de natureza
        testes = [
            ("cafe", "Compra de café"),
            ("INSS", "INSS"),
            ("salario", "Salário"),
        ]

        for natureza_filtro, descricao in testes:
            print(f"\n{'=' * 80}")
            print(f"TESTE: {descricao} (natureza='{natureza_filtro}')")
            print("=" * 80)

            result = sql_tools._pesquisa_contas_a_pagar(natureza=natureza_filtro)

            # Extrai informações da resposta
            import re

            # Total de registros
            match = re.search(r'Total de registros SQL: (\d+)', result)
            if match:
                print(f"Registros: {match.group(1)}")

            # Valor total
            match = re.search(r'Valor total a pagar: R\$ ([\d\.,]+)', result)
            if match:
                print(f"Total: R$ {match.group(1)}")

            # Top 3 fornecedores
            fornecedores = re.findall(r'"fornecedor": "([^"]+)"', result)
            if fornecedores:
                print(f"Top 3 fornecedores: {fornecedores[:3]}")

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
    test_natureza()
