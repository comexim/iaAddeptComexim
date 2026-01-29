"""
Verifica se o filtro mes='01' está retornando apenas janeiro
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_mes_verification():
    """Verifica quais meses estão vindo do banco"""
    print("=" * 80)
    print("VERIFICACAO DE MESES - IA_Orcamento WHERE ano=2026 AND mes='01'")
    print("=" * 80)

    try:
        print("\n1. Conectando...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Executa com filtro mes='01'
        print("2. Executando: WHERE ano=2026 AND mes='01'")
        filters = {"ano": 2026, "mes": "01"}
        results = sql_client.execute_function("IA_Orcamento", filters)

        if not results:
            print("[AVISO] Nenhum registro")
            return

        print(f"[OK] {len(results)} registros\n")

        # Agrupa por mês
        meses = defaultdict(lambda: {"count": 0, "orcado": 0})
        anos = defaultdict(lambda: {"count": 0, "orcado": 0})

        for row in results:
            mes = row.get("mes", "?")
            ano = row.get("ano", "?")
            orcado = row.get("orcado", 0) or 0

            meses[mes]["count"] += 1
            meses[mes]["orcado"] += orcado

            anos[ano]["count"] += 1
            anos[ano]["orcado"] += orcado

        print("3. MESES RETORNADOS:")
        print("-" * 80)
        for mes in sorted(meses.keys()):
            data = meses[mes]
            print(f"  Mes {mes}: {data['count']} registros, R$ {data['orcado']:,.2f}")

        print("\n4. ANOS RETORNADOS:")
        print("-" * 80)
        for ano in sorted(anos.keys()):
            data = anos[ano]
            print(f"  Ano {ano}: {data['count']} registros, R$ {data['orcado']:,.2f}")

        # Verifica se tem registros duplicados por descricao
        print("\n5. VERIFICACAO DE DUPLICATAS POR DESCRICAO:")
        print("-" * 80)
        desc_count = defaultdict(int)
        for row in results:
            desc = row.get("descricao", "").strip()
            desc_count[desc] += 1

        duplicates = {k: v for k, v in desc_count.items() if v > 1}
        if duplicates:
            print("ENCONTRADAS DUPLICATAS:")
            for desc, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True):
                print(f"  '{desc}': {count} registros")
        else:
            print("  Nenhuma duplicata encontrada (cada descricao aparece 1x)")

        # Mostra primeiros 5 registros para debug
        print("\n6. PRIMEIROS 5 REGISTROS (para debug):")
        print("-" * 80)
        for i, row in enumerate(results[:5], 1):
            print(f"\nRegistro {i}:")
            print(f"  ano: {row.get('ano')}, mes: {row.get('mes')}")
            print(f"  grupo: {row.get('grupo')}, descricao: {row.get('descricao')}")
            print(f"  orcado: R$ {row.get('orcado', 0):,.2f}")

        print("\n" + "=" * 80)
        print("[OK] VERIFICACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_mes_verification()
