"""
Valida: Saldo total em dólares
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal
from collections import defaultdict

def test_dolares():
    """Valida saldo total em dólares"""
    print("=" * 80)
    print("VALIDACAO - Saldo total em dólares")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total em dólares: R$ 412.499,83")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando TODAS as contas bancárias")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)

        if not result:
            print("[ERRO] Nenhuma conta encontrada")
            return

        print(f"Total de contas no banco: {len(result)}")

        print("\n4. Filtrando por moeda = Dólares")
        print("-" * 80)

        contas_dolares = []
        total_dolares = 0

        for r in result:
            moeda = r.get("moeda", "").strip()
            if moeda in ["Dolares", "Dolar"]:
                saldo = r.get("saldo", 0)

                # Converte saldo
                if saldo is None:
                    saldo = 0
                elif isinstance(saldo, Decimal):
                    saldo = float(saldo)
                elif isinstance(saldo, str):
                    try:
                        saldo = float(saldo)
                    except:
                        saldo = 0

                contas_dolares.append(r)
                total_dolares += saldo

                banco = r.get("banco", "")
                agencia = r.get("agencia", "")
                conta = r.get("conta", "")
                print(f"  {banco:30} Ag:{agencia:6} Conta:{conta:15} R$ {saldo:>15,.2f}")

        print("\n5. TOTAL EM DÓLARES:")
        print("=" * 80)
        print(f"Total de contas em dólares: {len(contas_dolares)}")
        print(f"Saldo total em dólares: R$ {total_dolares:,.2f}")

        print("\n6. COMPARAÇÃO COM IA:")
        print("=" * 80)

        ia_dolares = 412499.83

        print(f"\nIA disse:    R$ {ia_dolares:,.2f}")
        print(f"Banco tem:   R$ {total_dolares:,.2f}")
        print(f"Diferença:   R$ {abs(total_dolares - ia_dolares):,.2f}")

        if abs(total_dolares - ia_dolares) < 1:
            print("[OK] Valores EXATOS!")
        else:
            percentual = (abs(total_dolares - ia_dolares) / ia_dolares * 100) if ia_dolares > 0 else 0
            if percentual < 1:
                print(f"[OK] Diferença mínima ({percentual:.2f}%)")
            else:
                print(f"[X] INCORRETO - Diferença de {percentual:.2f}%")

        print("\n7. Testando a tool diretamente")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Saldo em dólares"

        result_tool = sql_tools._pesquisa_saldo_bancario(banco=None)

        print("\nResposta da tool (primeiros 2000 chars):")
        print(result_tool[:2000])

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_dolares()
