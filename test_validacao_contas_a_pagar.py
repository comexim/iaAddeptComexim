"""
Valida dados de contas a pagar desde 12/12/2025
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal
from collections import defaultdict

def test_validacao_a_pagar():
    """Valida contas a pagar desde 12/12/2025"""
    print("=" * 80)
    print("VALIDACAO - Contas a pagar desde 12/12/2025")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. VERIFICACAO NO BANCO:")
        print("-" * 80)
        print("Consultando: IA_ContasAPagar WHERE vencimento >= '20251212'")

        result = sql_client.execute_function("dbo.IA_ContasAPagar", filters={"vencimento": "20251212"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        print(f"\nTotal de registros: {len(result)}")

        # Calcula total
        total_valor = 0
        for r in result:
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

        print(f"Valor total a pagar: R$ {total_valor:,.2f}")

        # Agrupa por fornecedor
        por_fornecedor = defaultdict(lambda: {"valor": 0, "quantidade": 0, "naturezas": set()})

        for r in result:
            fornecedor = r.get("fornecedor", "SEM FORNECEDOR").strip() or "SEM FORNECEDOR"
            valor = r.get("valor", 0)
            natureza = r.get("natureza", "").strip()

            if isinstance(valor, Decimal):
                valor = float(valor)
            elif isinstance(valor, str):
                try:
                    valor = float(valor)
                except:
                    valor = 0
            elif not isinstance(valor, (int, float)):
                valor = 0

            por_fornecedor[fornecedor]["valor"] += valor
            por_fornecedor[fornecedor]["quantidade"] += 1
            if natureza:
                por_fornecedor[fornecedor]["naturezas"].add(natureza)

        # Ordena por valor absoluto
        fornecedores_ordenados = sorted(por_fornecedor.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

        print("\n" + "=" * 80)
        print("TOP 10 MAIORES FORNECEDORES A PAGAR:")
        print("=" * 80)
        for i, (fornecedor, dados) in enumerate(fornecedores_ordenados[:10], 1):
            nome_curto = fornecedor[:40] if len(fornecedor) > 40 else fornecedor
            naturezas = ", ".join(sorted(dados["naturezas"]))[:40]
            print(f"{i:2}. {nome_curto:40} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} títulos)")
            if naturezas:
                print(f"     Naturezas: {naturezas}")

        # Analisa naturezas
        print("\n" + "=" * 80)
        print("ANÁLISE POR NATUREZA:")
        print("=" * 80)

        por_natureza = defaultdict(lambda: {"valor": 0, "quantidade": 0})
        for r in result:
            natureza = r.get("natureza", "SEM NATUREZA").strip() or "SEM NATUREZA"
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

            por_natureza[natureza]["valor"] += valor
            por_natureza[natureza]["quantidade"] += 1

        naturezas_ordenadas = sorted(por_natureza.items(), key=lambda x: abs(x[1]["valor"]), reverse=True)

        print("\nTop 10 naturezas (por valor):")
        for i, (natureza, dados) in enumerate(naturezas_ordenadas[:10], 1):
            print(f"{i:2}. {natureza:45} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} títulos)")

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
    test_validacao_a_pagar()
