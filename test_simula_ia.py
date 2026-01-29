"""
Simula exatamente o que a IA faz quando recebe a pergunta
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.utils.date_parser import date_parser
import logging

# Ativa logs detalhados
logging.basicConfig(level=logging.DEBUG)

def test_simula_ia():
    """Simula IA recebendo: 'Quanto tenho a pagar desde 12/12/2025?'"""
    print("=" * 80)
    print("SIMULACAO - IA recebe: 'Quanto tenho a pagar desde 12/12/2025?'")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        # Simula usuário
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        # Cria SQLTools (simula o agente)
        print("2. IA identifica que deve usar pesquisa_contas_a_pagar")
        print("-" * 80)

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto tenho a pagar desde 12/12/2025?"

        # Testa diferentes variações que a IA pode passar
        testes = [
            "desde 12/12/2025",
            "12/12/2025",
            "20251212"
        ]

        for i, data_param in enumerate(testes, 1):
            print(f"\n{'=' * 80}")
            print(f"TESTE {i}: _pesquisa_contas_a_pagar(data_vencimento='{data_param}')")
            print("=" * 80)

            # Primeiro, mostra o que o parser faz
            print(f"\nPasso 1: date_parser.parse_natural_date('{data_param}')")
            parsed = date_parser.parse_natural_date(data_param)
            print(f"  Resultado: {parsed}")

            # Agora chama a tool
            print(f"\nPasso 2: Chamando tool...")
            result = sql_tools._pesquisa_contas_a_pagar(data_vencimento=data_param)

            print(f"\nPasso 3: Resultado da tool:")
            if "Nenhuma conta" in result:
                print(f"  [X] ERRO: Retornou 'Nenhuma conta'")
                print(f"  Resposta: {result[:200]}")
            else:
                print(f"  [OK] Retornou dados")
                # Extrai total
                import re
                match = re.search(r'Valor total a pagar: R\$ ([\d\.,]+)', result)
                if match:
                    print(f"  Total: R$ {match.group(1)}")
                match = re.search(r'Total de registros SQL: (\d+)', result)
                if match:
                    print(f"  Registros: {match.group(1)}")

        print("\n" + "=" * 80)
        print("[OK] SIMULACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_simula_ia()
