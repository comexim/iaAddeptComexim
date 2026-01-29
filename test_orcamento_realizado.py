"""
Investiga diferença no valor realizado de janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_realizado():
    """Testa valor realizado em detalhes"""
    print("=" * 80)
    print("INVESTIGACAO - VALOR REALIZADO JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando e consultando...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Query com filtro janeiro 2026
        print("2. Executando: WHERE ano=2026 AND mes='01'")
        filters = {"ano": 2026, "mes": "01"}
        results = sql_client.execute_function("IA_Orcamento", filters)

        if not results:
            print("[AVISO] Nenhum registro")
            return

        print(f"[OK] {len(results)} registros\n")

        # Agrupa por descricao
        categorias = defaultdict(lambda: {
            "orcado": 0,
            "realizado": 0,
            "saldo": 0,
            "count": 0
        })

        for row in results:
            desc = row.get("descricao", "").strip()
            if not desc:
                desc = row.get("grupo", "SEM GRUPO")

            categorias[desc]["orcado"] += row.get("orcado", 0) or 0
            categorias[desc]["realizado"] += row.get("realizado", 0) or 0
            categorias[desc]["saldo"] += row.get("saldo", 0) or 0
            categorias[desc]["count"] += 1

        # Calcula totais
        total_orcado = sum(c["orcado"] for c in categorias.values())
        total_realizado = sum(c["realizado"] for c in categorias.values())
        total_saldo = sum(c["saldo"] for c in categorias.values())

        print("3. TOTAIS CALCULADOS PELO PYTHON:")
        print("-" * 80)
        print(f"Total Orcado:    R$ {total_orcado:,.2f}")
        print(f"Total Realizado: R$ {total_realizado:,.2f}")
        print(f"Total Saldo:     R$ {total_saldo:,.2f}")

        print("\n4. O QUE A IA DISSE:")
        print("-" * 80)
        print(f"Total Orcado:    R$ 11.903.243,89")
        print(f"Total Realizado: R$ 6.921.844,99")
        print(f"Total Saldo:     R$ 4.981.398,90")

        print("\n5. COMPARACAO:")
        print("-" * 80)
        diff_orcado = 11903243.89 - total_orcado
        diff_realizado = 6921844.99 - total_realizado
        diff_saldo = 4981398.90 - total_saldo

        print(f"Diferenca Orcado:    R$ {diff_orcado:,.2f}")
        print(f"Diferenca Realizado: R$ {diff_realizado:,.2f}")
        print(f"Diferenca Saldo:     R$ {diff_saldo:,.2f}")

        # Busca categorias com valor realizado próximo da diferença
        print("\n6. CATEGORIAS COM REALIZADO PROXIMO DA DIFERENCA (R$ 71k):")
        print("-" * 80)
        for desc, data in sorted(categorias.items(), key=lambda x: abs(x[1]["realizado"] - 71062), reverse=False)[:10]:
            if data["realizado"] > 0:
                print(f"{desc[:50]:50s} R$ {data['realizado']:>15,.2f}")

        # Mostra TOP 10 realizados
        print("\n7. TOP 10 CATEGORIAS POR REALIZADO:")
        print("-" * 80)
        top_realizado = sorted(categorias.items(), key=lambda x: x[1]["realizado"], reverse=True)[:10]
        for i, (desc, data) in enumerate(top_realizado, 1):
            print(f"{i:2d}. {desc[:40]:40s} R$ {data['realizado']:>15,.2f}")

        # Verifica soma direta dos registros SQL
        print("\n8. SOMA DIRETA DOS REGISTROS SQL (sem agregacao):")
        print("-" * 80)
        soma_direta_orcado = sum(row.get("orcado", 0) or 0 for row in results)
        soma_direta_realizado = sum(row.get("realizado", 0) or 0 for row in results)
        soma_direta_saldo = sum(row.get("saldo", 0) or 0 for row in results)

        print(f"Soma Direta Orcado:    R$ {soma_direta_orcado:,.2f}")
        print(f"Soma Direta Realizado: R$ {soma_direta_realizado:,.2f}")
        print(f"Soma Direta Saldo:     R$ {soma_direta_saldo:,.2f}")

        print("\n" + "=" * 80)
        print("[OK] INVESTIGACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_realizado()
