"""
Lista todos os bancos com 'BB' ou 'Brasil' no nome
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_bancos():
    """Lista bancos com Brasil ou BB"""
    print("=" * 80)
    print("BANCOS COM 'BRASIL' OU 'BB' NO NOME")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Buscando TODAS as contas")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_SaldoBancario", filters=None)

        if not result:
            print("[ERRO] Nenhuma conta encontrada")
            return

        print(f"Total de contas: {len(result)}")

        print("\n3. TODOS OS BANCOS ÚNICOS:")
        print("=" * 80)

        bancos_saldos = {}
        for r in result:
            banco = r.get("banco", "").strip()
            moeda = r.get("moeda", "").strip() or "Reais"
            saldo = r.get("saldo", 0)

            if isinstance(saldo, Decimal):
                saldo = float(saldo)
            elif saldo is None:
                saldo = 0

            chave = f"{banco}|{moeda}"
            if chave not in bancos_saldos:
                bancos_saldos[chave] = 0
            bancos_saldos[chave] += saldo

        # Ordena por nome do banco
        for chave in sorted(bancos_saldos.keys()):
            banco, moeda = chave.split("|")
            saldo = bancos_saldos[chave]
            print(f"{banco:40} {moeda:10} R$ {saldo:>15,.2f}")

        print("\n4. FILTRANDO POR 'BB' OU 'BRASIL':")
        print("=" * 80)

        encontrados = []
        for chave in sorted(bancos_saldos.keys()):
            banco, moeda = chave.split("|")
            banco_upper = banco.upper()

            if "BB" in banco_upper or "BRASIL" in banco_upper:
                saldo = bancos_saldos[chave]
                print(f"{banco:40} {moeda:10} R$ {saldo:>15,.2f}")
                encontrados.append((banco, moeda, saldo))

        if not encontrados:
            print("\n[!] NENHUM banco com 'BB' ou 'BRASIL' encontrado!")

        print("\n5. Verificando o que a IA pode estar usando:")
        print("=" * 80)
        print("\nPossibilidades:")
        print("1. 'Banco do Brasil' é um nome que não existe no banco")
        print("2. 'BB' é abreviação que deveria mapear para outro nome")
        print("3. IA está inventando valores")

        print("\n" + "=" * 80)
        print("[OK] LISTAGEM CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_bancos()
