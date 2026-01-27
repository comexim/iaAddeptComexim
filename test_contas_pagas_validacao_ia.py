"""
Testa se a IA consegue interpretar contas pagas corretamente
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_validacao_ia():
    """Valida dados para teste com IA"""
    print("=" * 80)
    print("VALIDACAO - Contas Pagas para IA")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Consultando contas pagas de dezembro 2025...")
        result = sql_client.execute_function("dbo.IA_ContasPagas", filters={"emissao": "20251201"})

        if not result:
            print("[ERRO] Nenhum resultado")
            return

        print(f"[OK] {len(result)} registros retornados\n")

        # Calcula total
        total_valor = 0
        for r in result:
            valor = r.get("valor", None)
            if valor:
                if isinstance(valor, Decimal):
                    total_valor += float(valor)
                elif isinstance(valor, (int, float)):
                    total_valor += valor

        print("=" * 80)
        print("RESUMO PARA IA:")
        print("=" * 80)
        print(f"Total de pagamentos: {len(result)}")
        print(f"Valor total: R$ {total_valor:,.2f}")
        print()
        print("NOTA: Valores negativos sao normais em contabilidade")
        print("      (contas pagas = despesas = debito = valor negativo)")
        print()

        # Mostra alguns exemplos
        print("Exemplos de pagamentos (primeiros 5):")
        print("-" * 80)
        for i, r in enumerate(result[:5], 1):
            fornecedor = r.get("fornecedor", "N/A")
            valor = r.get("valor", 0)
            if isinstance(valor, Decimal):
                valor = float(valor)
            natureza = r.get("natureza", "N/A")
            banco = r.get("banco", "N/A")
            emissao = r.get("emissao", "N/A")

            print(f"\n{i}. Fornecedor: {fornecedor[:50]}")
            print(f"   Valor: R$ {valor:,.2f}")
            print(f"   Natureza: {natureza}")
            print(f"   Banco: {banco}")
            print(f"   Emissao: {emissao}")

        # Agrupa por natureza para dar contexto
        from collections import defaultdict
        por_natureza = defaultdict(lambda: {"valor": 0, "quantidade": 0})

        for r in result:
            natureza = r.get("natureza", "SEM NATUREZA").strip() or "SEM NATUREZA"
            valor = r.get("valor", 0)
            if isinstance(valor, Decimal):
                valor = float(valor)

            por_natureza[natureza]["valor"] += valor
            por_natureza[natureza]["quantidade"] += 1

        print("\n\n" + "=" * 80)
        print("DESPESAS POR NATUREZA (Top 15):")
        print("=" * 80)

        naturezas_ordenadas = sorted(por_natureza.items(), key=lambda x: x[1]["valor"])

        for i, (natureza, dados) in enumerate(naturezas_ordenadas[:15], 1):
            print(f"{i:2}. {natureza:45} R$ {dados['valor']:>15,.2f}  ({dados['quantidade']:>4} pagamentos)")

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
    test_validacao_ia()
