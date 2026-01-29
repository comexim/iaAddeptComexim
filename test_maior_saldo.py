"""
Valida: Maior saldo bancário
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from decimal import Decimal
from collections import defaultdict

def test_maior_saldo():
    """Valida qual banco tem o maior saldo"""
    print("=" * 80)
    print("VALIDACAO - Maior saldo bancário")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Maior saldo: Itaú Armazém com R$ 132.333,70")

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

        print("\n4. Agregando por banco (apenas Reais)")
        print("-" * 80)

        por_banco = defaultdict(float)

        for r in result:
            banco = r.get("banco", "").strip()
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

            # Considera apenas contas em Reais
            if moeda == "Reais":
                por_banco[banco] += saldo

        print("\n5. TOP 10 MAIORES SALDOS (Reais):")
        print("=" * 80)

        # Ordena por saldo (maior primeiro)
        bancos_ordenados = sorted(por_banco.items(), key=lambda x: x[1], reverse=True)

        for i, (banco, saldo) in enumerate(bancos_ordenados[:10], 1):
            print(f"{i:2}. {banco:40} R$ {saldo:>15,.2f}")

        print("\n6. COMPARAÇÃO COM IA:")
        print("=" * 80)

        maior_banco = bancos_ordenados[0] if bancos_ordenados else (None, 0)
        maior_nome, maior_saldo = maior_banco

        ia_banco = "ITAU ARMAZEM"
        ia_saldo = 132333.70

        print(f"\nIA disse:")
        print(f"  Banco: {ia_banco}")
        print(f"  Saldo: R$ {ia_saldo:,.2f}")

        print(f"\nBanco tem:")
        print(f"  Banco: {maior_nome}")
        print(f"  Saldo: R$ {maior_saldo:,.2f}")

        # Verifica se o banco da IA está nos top 10
        ia_banco_norm = ia_banco.upper().replace(" ", "")
        posicao_ia = None
        saldo_ia_real = None

        for i, (banco, saldo) in enumerate(bancos_ordenados, 1):
            banco_norm = banco.upper().replace(" ", "")
            if ia_banco_norm in banco_norm or banco_norm in ia_banco_norm:
                posicao_ia = i
                saldo_ia_real = saldo
                print(f"\n{banco} está na posição {i} com R$ {saldo:,.2f}")
                break

        if posicao_ia == 1:
            if abs(maior_saldo - ia_saldo) < 1:
                print("\n[OK] IA está 100% CORRETA!")
            else:
                print(f"\n[OK] IA identificou o banco correto, mas valor tem diferença de R$ {abs(maior_saldo - ia_saldo):,.2f}")
        elif posicao_ia and posicao_ia <= 3:
            print(f"\n[!] IA está INCORRETA - {ia_banco} está na posição {posicao_ia}, não é o maior")
            print(f"    O maior saldo é: {maior_nome} com R$ {maior_saldo:,.2f}")
        else:
            print(f"\n[X] IA está INCORRETA - {ia_banco} não está entre os maiores saldos")
            print(f"    O maior saldo é: {maior_nome} com R$ {maior_saldo:,.2f}")

        print("\n7. Considerando TODAS as moedas:")
        print("=" * 80)

        # Agora considera todas as moedas
        por_banco_moeda = {}
        for r in result:
            banco = r.get("banco", "").strip()
            moeda = r.get("moeda", "").strip() or "Reais"
            saldo = r.get("saldo", 0)

            if saldo is None:
                saldo = 0
            elif isinstance(saldo, Decimal):
                saldo = float(saldo)
            elif isinstance(saldo, str):
                try:
                    saldo = float(saldo)
                except:
                    saldo = 0

            chave = f"{banco} ({moeda})"
            if chave not in por_banco_moeda:
                por_banco_moeda[chave] = 0
            por_banco_moeda[chave] += saldo

        # Top 10 todas as moedas
        bancos_todas_moedas = sorted(por_banco_moeda.items(), key=lambda x: x[1], reverse=True)

        print("\nTOP 10 MAIORES SALDOS (todas as moedas):")
        for i, (banco_moeda, saldo) in enumerate(bancos_todas_moedas[:10], 1):
            print(f"{i:2}. {banco_moeda:45} R$ {saldo:>15,.2f}")

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
    test_maior_saldo()
