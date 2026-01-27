"""
Debug: testa se dezembro 2025 funciona
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal

def test_dezembro_2025():
    """Testa dezembro 2025"""
    print("=" * 80)
    print("DEBUG - dezembro de 2025")
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

        print("2. Testando tool com 'dezembro de 2025'")
        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto pagamos em dezembro de 2025?"

        try:
            result = sql_tools._pesquisa_contas_pagas(data_inicio="dezembro de 2025")

            if result:
                print(f"[OK] Tool retornou resultado")
                print(f"Tamanho: {len(result)} caracteres")
                print(f"\nPrimeiros 500 chars:")
                print("-" * 80)
                print(result[:500])
            else:
                print("[ERRO] Tool retornou vazio")

        except Exception as e:
            print(f"[ERRO] Excecao ao chamar tool: {e}")
            import traceback
            traceback.print_exc()

        print("\n\n3. Testando date parser diretamente:")
        print("-" * 80)
        from app.utils.date_parser import DateParser

        testes = [
            "dezembro 2025",
            "dezembro de 2025",
            "12/2025",
            "dez 2025",
            "dez/2025"
        ]

        for texto in testes:
            parsed = DateParser.parse_natural_date(texto)
            if parsed:
                print(f"[OK] '{texto}' -> {parsed.get('data_inicio')}")
            else:
                print(f"[X] '{texto}' -> NAO PARSEADO")

        print("\n\n4. Verificacao direta no banco:")
        print("-" * 80)
        result_direto = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})

        if result_direto:
            total_valor = 0
            for r in result_direto:
                valor = r.get("valor", 0)
                if isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                total_valor += valor

            print(f"[OK] {len(result_direto)} registros")
            print(f"Valor total: R$ {abs(total_valor):,.2f}")
        else:
            print("[ERRO] Nenhum registro no banco")

    except Exception as e:
        print(f"\n[ERRO GERAL] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_dezembro_2025()
