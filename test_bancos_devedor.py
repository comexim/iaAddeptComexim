"""
Valida: Bancos com saldo devedor (negativos)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal
from collections import defaultdict

def test_devedor():
    """Valida bancos com saldo devedor"""
    print("=" * 80)
    print("VALIDACAO - Bancos com saldo devedor")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("1. Itaú Santos: R$ -1.410.034,65")
        print("2. ABC Brasil: R$ -101.027,78")

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

        print("\n4. Agregando por banco")
        print("-" * 80)

        por_banco = defaultdict(float)

        for r in result:
            banco = r.get("banco", "").strip()
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

            por_banco[banco] += saldo

        print("\n5. BANCOS COM SALDO NEGATIVO (devendo):")
        print("=" * 80)

        bancos_negativos = []
        for banco, saldo in por_banco.items():
            if saldo < 0:
                bancos_negativos.append((banco, saldo))

        # Ordena por valor absoluto (maior dívida primeiro)
        bancos_negativos.sort(key=lambda x: x[1])

        if not bancos_negativos:
            print("\n[!] NENHUM banco com saldo negativo encontrado!")
        else:
            for i, (banco, saldo) in enumerate(bancos_negativos, 1):
                print(f"{i}. {banco:30} R$ {saldo:>15,.2f}")

        print("\n6. COMPARAÇÃO COM IA:")
        print("=" * 80)

        ia_valores = {
            "ITAU STOS": -1410034.65,
            "ABC BRASIL": -101027.78
        }

        matches = 0
        for banco_ia, valor_ia in ia_valores.items():
            # Busca o banco no resultado (normalizado)
            encontrado = False
            for banco, saldo in bancos_negativos:
                banco_norm = banco.upper().replace(" ", "")
                banco_ia_norm = banco_ia.upper().replace(" ", "")

                if banco_ia_norm in banco_norm or banco_norm in banco_ia_norm:
                    encontrado = True
                    print(f"\n{banco}:")
                    print(f"  IA disse:    R$ {valor_ia:,.2f}")
                    print(f"  Banco tem:   R$ {saldo:,.2f}")
                    print(f"  Diferença:   R$ {abs(saldo - valor_ia):,.2f}")

                    if abs(saldo - valor_ia) < 1:
                        print("  [OK] Valores EXATOS!")
                        matches += 1
                    else:
                        percentual = (abs(saldo - valor_ia) / abs(valor_ia) * 100) if valor_ia != 0 else 0
                        if percentual < 1:
                            print(f"  [OK] Diferença mínima ({percentual:.2f}%)")
                            matches += 1
                        else:
                            print(f"  [X] INCORRETO - Diferença de {percentual:.2f}%")
                    break

            if not encontrado:
                print(f"\n{banco_ia}:")
                print(f"  [X] NÃO ENCONTRADO no banco de dados!")

        print("\n7. RESUMO:")
        print("=" * 80)
        print(f"Total de bancos com saldo negativo: {len(bancos_negativos)}")
        print(f"Bancos mencionados pela IA: {len(ia_valores)}")
        print(f"Matches corretos: {matches}/{len(ia_valores)}")

        if matches == len(ia_valores) and len(bancos_negativos) == len(ia_valores):
            print("\n[OK] IA está 100% CORRETA!")
        elif matches == len(ia_valores):
            print(f"\n[!] IA está correta, mas existem {len(bancos_negativos) - len(ia_valores)} banco(s) adicional(is) com saldo negativo")
        else:
            print("\n[X] IA tem valores INCORRETOS")

        print("\n8. Testando a tool diretamente")
        print("=" * 80)

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "Quais bancos estou devendo?"

        result_tool = sql_tools._pesquisa_saldo_bancario(banco=None)

        # Mostra as linhas com saldo negativo
        print("\nLinhas com saldo negativo na resposta da tool:")
        linhas = result_tool.split('\n')
        for linha in linhas:
            if '"saldo": -' in linha or 'NEGATIVO' in linha.upper() or 'DEVEDOR' in linha.upper():
                print(linha)

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
    test_devedor()
