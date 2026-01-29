"""
Valida: Saldo do Banco do Brasil
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal
from collections import defaultdict

def test_bb():
    """Valida saldo do BB"""
    print("=" * 80)
    print("VALIDACAO - Saldo do Banco do Brasil")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Em Reais: R$ 67.988,96")
        print("Em Dólares: R$ 841,41")

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

        print("\n4. Filtrando por Banco do Brasil")
        print("-" * 80)

        # Busca todas as variações de "Banco do Brasil"
        bb_accounts = []
        for r in result:
            banco = r.get("banco", "").upper()
            # Procura por "BANCO DO BRASIL", "BB", "BRASIL", etc
            if "BRASIL" in banco or banco.strip() == "BB" or "B BRASIL" in banco or "BCO BRASIL" in banco:
                bb_accounts.append(r)
                print(f"  Encontrado: {r.get('banco', '')} - Ag: {r.get('agencia', '')} Conta: {r.get('conta', '')}")

        if not bb_accounts:
            print("\n[X] NENHUMA conta do Banco do Brasil encontrada!")
            print("\nBancos disponíveis (primeiros 20):")
            bancos_unicos = set()
            for r in result:
                banco = r.get("banco", "").strip()
                if banco:
                    bancos_unicos.add(banco)
            for banco in sorted(bancos_unicos)[:20]:
                print(f"  - {banco}")
            return

        print(f"\nTotal de contas BB encontradas: {len(bb_accounts)}")

        print("\n5. Agregando por moeda")
        print("-" * 80)

        por_moeda = defaultdict(float)

        for r in bb_accounts:
            moeda = r.get("moeda", "").strip() or "Reais"
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

            por_moeda[moeda] += saldo

            banco = r.get("banco", "")
            agencia = r.get("agencia", "")
            conta = r.get("conta", "")
            print(f"  {banco:30} Ag:{agencia:6} Conta:{conta:15} {moeda:10} R$ {saldo:>15,.2f}")

        print("\n6. TOTAIS POR MOEDA:")
        print("=" * 80)

        for moeda in sorted(por_moeda.keys()):
            total = por_moeda[moeda]
            print(f"{moeda}: R$ {total:,.2f}")

        print("\n7. COMPARAÇÃO COM IA:")
        print("=" * 80)

        ia_reais = 67988.96
        ia_dolares = 841.41

        total_reais = por_moeda.get("Reais", 0) + por_moeda.get("Real", 0)
        total_dolares = por_moeda.get("Dolares", 0) + por_moeda.get("Dolar", 0)

        print(f"\nReais:")
        print(f"  IA disse:    R$ {ia_reais:,.2f}")
        print(f"  Banco tem:   R$ {total_reais:,.2f}")
        print(f"  Diferença:   R$ {abs(total_reais - ia_reais):,.2f}")

        if abs(total_reais - ia_reais) < 1:
            print("  [OK] Valores EXATOS!")
        else:
            percentual = (abs(total_reais - ia_reais) / ia_reais * 100) if ia_reais > 0 else 0
            if percentual < 1:
                print(f"  [OK] Diferença mínima ({percentual:.2f}%)")
            else:
                print(f"  [X] INCORRETO - Diferença de {percentual:.2f}%")

        print(f"\nDólares:")
        print(f"  IA disse:    R$ {ia_dolares:,.2f}")
        print(f"  Banco tem:   R$ {total_dolares:,.2f}")
        print(f"  Diferença:   R$ {abs(total_dolares - ia_dolares):,.2f}")

        if abs(total_dolares - ia_dolares) < 1:
            print("  [OK] Valores EXATOS!")
        else:
            percentual = (abs(total_dolares - ia_dolares) / ia_dolares * 100) if ia_dolares > 0 else 0
            if percentual < 1:
                print(f"  [OK] Diferença mínima ({percentual:.2f}%)")
            else:
                print(f"  [X] INCORRETO - Diferença de {percentual:.2f}%")

        print("\n8. Testando a tool diretamente")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quanto tenho no Banco do Brasil?"

        result_tool = sql_tools._pesquisa_saldo_bancario(banco="Banco do Brasil")

        print("\nResposta da tool:")
        print(result_tool[:1500])

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
    test_bb()
