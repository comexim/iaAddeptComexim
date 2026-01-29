"""
Validação: Quanto devo para a FOLHA (desde hoje)?
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from datetime import datetime

def test_validacao():
    """Valida resposta da IA sobre FOLHA com filtro de data"""
    print("=" * 80)
    print("VALIDACAO - Quanto devo para a FOLHA (testando filtros)")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        valor_ia = 57631193.83
        qtd_ia = 86
        print(f"Total: R$ {valor_ia:,.2f}")
        print(f"Quantidade: {qtd_ia} títulos")
        print("Próximos vencimentos: 29/01/2026 e 30/01/2026")

        print("\n3. TESTANDO DIFERENTES FILTROS:")
        print("=" * 80)

        # Busca todas as contas a pagar
        result_all = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)

        # Data de hoje
        hoje = datetime.now().strftime('%Y%m%d')
        print(f"\nHoje: {hoje}")

        # Testa diferentes cenários
        cenarios = [
            ("Todas as contas", None),
            (f"Desde hoje ({hoje})", hoje),
            ("Desde 27/01/2026", "20260127"),
            ("Desde 28/01/2026", "20260128"),
            ("Desde 29/01/2026", "20260129"),
        ]

        for descricao, data_filtro in cenarios:
            print(f"\n{'-' * 80}")
            print(f"CENÁRIO: {descricao}")
            print("-" * 80)

            if data_filtro:
                folha_titulos = [r for r in result_all
                                if "FOLHA" in str(r.get("fornecedor", "")).upper()
                                and r.get("vencimento", "") >= data_filtro]
            else:
                folha_titulos = [r for r in result_all
                                if "FOLHA" in str(r.get("fornecedor", "")).upper()]

            total_valor = 0
            vencimentos = []

            for r in folha_titulos:
                valor = r.get("valor", 0)

                if valor is None:
                    valor = 0
                elif isinstance(valor, Decimal):
                    valor = float(valor)
                elif isinstance(valor, str):
                    try:
                        valor = float(valor)
                    except:
                        valor = 0
                elif not isinstance(valor, (int, float)):
                    valor = 0

                total_valor += valor

                vencimento = r.get("vencimento", "").strip()
                if vencimento:
                    vencimentos.append(vencimento)

            print(f"Títulos: {len(folha_titulos)}")
            print(f"Total: R$ {total_valor:,.2f}")

            # Verifica se bate com a IA
            diferenca = abs(total_valor - valor_ia)
            if diferenca < 100:
                print(f"[OK] MATCH COM A IA! (diferenca: R$ {diferenca:,.2f})")
            else:
                print(f"  Diferenca da IA: R$ {diferenca:,.2f}")

            if len(folha_titulos) == qtd_ia:
                print(f"[OK] Quantidade bate com a IA!")

            # Mostra próximos vencimentos
            vencimentos_unicos = sorted(set(vencimentos))[:3]
            print(f"Próximos vencimentos: {vencimentos_unicos}")

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
    test_validacao()
