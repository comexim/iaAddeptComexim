"""
Debug: Compara janeiro inteiro vs próximos 7 dias
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_debug():
    """Debug detalhado"""
    print("=" * 80)
    print("DEBUG - Janeiro inteiro vs Próximos 7 dias")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        # Busca TODOS os registros
        print("\n2. Buscando TODOS os registros de contas a receber...")
        result_all = sql_client.execute_function("dbo.IA_ContasAReceber", filters=None)
        print(f"Total de registros (sem filtro): {len(result_all) if result_all else 0}")

        if not result_all:
            return

        # Conta por data de vencimento
        print("\n3. DISTRIBUIÇÃO POR DATA DE VENCIMENTO:")
        print("=" * 80)

        por_data = defaultdict(lambda: {"qtd": 0, "valor": 0})

        for r in result_all:
            venc = r.get("vencimentoReal", "")
            valor = r.get("valor", 0)

            if isinstance(valor, Decimal):
                valor = float(valor)
            elif valor is None:
                valor = 0

            por_data[venc]["qtd"] += 1
            por_data[venc]["valor"] += valor

        # Filtra apenas janeiro e início de fevereiro
        print("\nJANEIRO 2026:")
        print("-" * 80)

        total_jan = 0
        qtd_jan = 0
        for data in sorted(por_data.keys()):
            if "202601" in data:
                print(f"{data}: {por_data[data]['qtd']:3} títulos, R$ {por_data[data]['valor']:>15,.2f}")
                total_jan += por_data[data]["valor"]
                qtd_jan += por_data[data]["qtd"]

        print(f"\nTOTAL JANEIRO: {qtd_jan} títulos, R$ {total_jan:,.2f}")

        # Últimos 5 dias de janeiro
        print("\n" + "-" * 80)
        print("ÚLTIMOS 5 DIAS DE JANEIRO (27/01 a 31/01):")
        print("-" * 80)

        total_ultimos_5 = 0
        qtd_ultimos_5 = 0
        for data in sorted(por_data.keys()):
            if data >= "20260127" and data <= "20260131":
                print(f"{data}: {por_data[data]['qtd']:3} títulos, R$ {por_data[data]['valor']:>15,.2f}")
                total_ultimos_5 += por_data[data]["valor"]
                qtd_ultimos_5 += por_data[data]["qtd"]

        print(f"\nTOTAL ÚLTIMOS 5 DIAS: {qtd_ultimos_5} títulos, R$ {total_ultimos_5:,.2f}")

        # Primeiros dias de fevereiro
        print("\n" + "-" * 80)
        print("FEVEREIRO 2026 (primeiros dias):")
        print("-" * 80)

        total_fev = 0
        qtd_fev = 0
        for data in sorted(por_data.keys()):
            if "202602" in data and data <= "20260205":
                print(f"{data}: {por_data[data]['qtd']:3} títulos, R$ {por_data[data]['valor']:>15,.2f}")
                total_fev += por_data[data]["valor"]
                qtd_fev += por_data[data]["qtd"]

        print(f"\nTOTAL PRIMEIROS DIAS FEV: {qtd_fev} títulos, R$ {total_fev:,.2f}")

        # Próximos 7 dias (27/01 a 02/02)
        print("\n" + "=" * 80)
        print("PRÓXIMOS 7 DIAS (27/01 a 02/02):")
        print("=" * 80)

        total_7dias = 0
        qtd_7dias = 0
        for data in sorted(por_data.keys()):
            if data >= "20260127" and data <= "20260202":
                print(f"{data}: {por_data[data]['qtd']:3} títulos, R$ {por_data[data]['valor']:>15,.2f}")
                total_7dias += por_data[data]["valor"]
                qtd_7dias += por_data[data]["qtd"]

        print(f"\nTOTAL PRÓXIMOS 7 DIAS: {qtd_7dias} títulos, R$ {total_7dias:,.2f}")

        # Comparação
        print("\n" + "=" * 80)
        print("COMPARAÇÃO:")
        print("=" * 80)
        print(f"Janeiro inteiro (01/01 a 31/01):  {qtd_jan:3} títulos, R$ {total_jan:>15,.2f}")
        print(f"Próximos 7 dias (27/01 a 02/02):  {qtd_7dias:3} títulos, R$ {total_7dias:>15,.2f}")
        print(f"\nDiferença: {qtd_7dias - qtd_jan:+3} títulos, R$ {total_7dias - total_jan:+,.2f}")

        # Mostra primeiros 26 dias de janeiro
        print("\n" + "-" * 80)
        print("PRIMEIROS 26 DIAS DE JANEIRO (01/01 a 26/01):")
        print("-" * 80)

        total_primeiros_26 = 0
        qtd_primeiros_26 = 0
        for data in sorted(por_data.keys()):
            if data >= "20260101" and data <= "20260126":
                if por_data[data]["qtd"] > 0:
                    print(f"{data}: {por_data[data]['qtd']:3} títulos, R$ {por_data[data]['valor']:>15,.2f}")
                total_primeiros_26 += por_data[data]["valor"]
                qtd_primeiros_26 += por_data[data]["qtd"]

        print(f"\nTOTAL PRIMEIROS 26 DIAS: {qtd_primeiros_26} títulos, R$ {total_primeiros_26:,.2f}")

        print("\n" + "=" * 80)
        print("[OK] DEBUG CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug()
