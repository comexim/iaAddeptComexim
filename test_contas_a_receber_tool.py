"""
Testa a tool de contas a receber
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_tool():
    """Testa tool com diferentes filtros"""
    print("=" * 80)
    print("TESTE - Tool IA_ContasAReceber")
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

        # Testa diferentes cenários
        testes = [
            ("Todas as contas (sem filtro)", None, None),
            ("Desde 12/01/2025", "20250112", None),
            ("Próximos 7 dias", "proximos 7 dias", None),
            ("Este mês", "este mes", None),
        ]

        for i, (descricao, data_param, cliente_param) in enumerate(testes, 1):
            print(f"\n{'=' * 80}")
            print(f"TESTE {i}: {descricao}")
            if data_param:
                print(f"  data_vencimento='{data_param}'")
            if cliente_param:
                print(f"  cliente='{cliente_param}'")
            print("=" * 80)

            sql_tools.user_query = descricao
            result = sql_tools._pesquisa_contas_a_receber(
                data_vencimento=data_param,
                cliente=cliente_param
            )

            # Extrai informações da resposta
            import re

            if "Nenhuma conta" in result:
                print("[X] Retornou: Nenhuma conta")
            else:
                # Total de registros
                match = re.search(r'Total de registros[^:]*: (\d+)', result)
                if match:
                    print(f"[OK] Registros: {match.group(1)}")

                # Valor total
                match = re.search(r'Valor total a receber: R\$ ([\d\.,]+)', result)
                if match:
                    print(f"[OK] Total: R$ {match.group(1)}")

        print("\n" + "=" * 80)
        print("[OK] TODOS OS TESTES CONCLUIDOS")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_tool()
