"""
Validação: Quanto devo para a FOLHA?
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao():
    """Valida resposta da IA sobre FOLHA"""
    print("=" * 80)
    print("VALIDACAO - Quanto devo para a FOLHA?")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. RESPOSTA DA IA:")
        print("-" * 80)
        print("Total: R$ 57.631.193,83")
        print("Quantidade: 86 títulos")
        print("Naturezas: PLR e Salário Fixo")
        print("Próximos vencimentos: 29/01/2026 e 30/01/2026")

        print("\n3. VERIFICACAO NO BANCO:")
        print("-" * 80)

        # Busca todas as contas a pagar
        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters=None)
        print(f"Total de registros SQL (todos fornecedores): {len(result) if result else 0}")

        if result:
            # Filtra por FOLHA
            folha_titulos = [r for r in result if "FOLHA" in str(r.get("fornecedor", "")).upper()]
            print(f"Total de títulos da FOLHA: {len(folha_titulos)}")

            if folha_titulos:
                # Calcula total e agrupa por natureza
                total_valor = 0
                naturezas = set()
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

                    natureza = r.get("natureza", "").strip()
                    if natureza:
                        naturezas.add(natureza)

                    vencimento = r.get("vencimento", "").strip()
                    if vencimento:
                        vencimentos.append(vencimento)

                print(f"\nValor total para FOLHA: R$ {total_valor:,.2f}")
                print(f"Naturezas encontradas: {sorted(list(naturezas))}")

                # Próximos 5 vencimentos
                vencimentos_unicos = sorted(set(vencimentos))[:5]
                print(f"\nPróximos 5 vencimentos:")
                for v in vencimentos_unicos:
                    # Formata de YYYYMMDD para DD/MM/YYYY
                    if len(v) == 8:
                        data_formatada = f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
                        print(f"  - {data_formatada} ({v})")

                print("\n" + "=" * 80)
                print("COMPARACAO COM RESPOSTA DA IA:")
                print("=" * 80)

                # Valida total
                valor_ia = 57631193.83
                diferenca = abs(total_valor - valor_ia)
                percentual = (diferenca / valor_ia * 100) if valor_ia > 0 else 0

                if diferenca < 100:
                    print(f"[OK] Valor total: R$ {total_valor:,.2f} (correto)")
                else:
                    print(f"[X] Valor total: IA disse R$ {valor_ia:,.2f}, Banco tem R$ {total_valor:,.2f}")
                    print(f"    Diferenca: R$ {diferenca:,.2f} ({percentual:.1f}%)")

                # Valida quantidade
                qtd_ia = 86
                if len(folha_titulos) == qtd_ia:
                    print(f"[OK] Quantidade de títulos: {len(folha_titulos)} (correto)")
                else:
                    print(f"[X] Quantidade: IA disse {qtd_ia}, Banco tem {len(folha_titulos)}")

                # Valida naturezas
                naturezas_ia = {"PLR", "SALARIO FIXO"}
                naturezas_normalizadas = {n.upper().replace("Á", "A") for n in naturezas}

                if naturezas_ia.issubset(naturezas_normalizadas):
                    print(f"[OK] Naturezas mencionadas estão corretas")
                else:
                    print(f"[X] Naturezas: IA mencionou {naturezas_ia}, banco tem {naturezas_normalizadas}")

                # Valida vencimentos
                vencimentos_ia = ["20260129", "20260130"]
                if all(v in vencimentos_unicos for v in vencimentos_ia):
                    print(f"[OK] Vencimentos mencionados estão corretos")
                else:
                    print(f"[INFO] Vencimentos: IA mencionou {vencimentos_ia}, primeiros do banco: {vencimentos_unicos[:5]}")

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
