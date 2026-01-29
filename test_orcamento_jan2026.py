"""
Script de teste para validar resposta de orçamento janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client


def test_orcamento_jan2026():
    """Testa orçamento de janeiro 2026"""
    print("=" * 80)
    print("TESTE ORCAMENTO - JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao SQL Server...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Executa query para janeiro 2026
        print("2. Executando query: WHERE ano=2026 AND mes='01'")
        filters = {"ano": 2026, "mes": "01"}
        results = sql_client.execute_function("IA_Orcamento", filters)

        if not results:
            print("[AVISO] Nenhum registro retornado")
            return

        print(f"[OK] {len(results)} registros retornados\n")

        # Calcula totais
        total_orcado = 0
        total_realizado = 0
        total_saldo = 0

        print("3. TOP 10 CATEGORIAS (por valor orçado):")
        print("-" * 80)

        # Agrupa por descrição
        categorias = {}
        for row in results:
            desc = row.get("descricao", "").strip()
            if desc not in categorias:
                categorias[desc] = {
                    "orcado": 0,
                    "realizado": 0,
                    "saldo": 0
                }
            categorias[desc]["orcado"] += row.get("orcado", 0) or 0
            categorias[desc]["realizado"] += row.get("realizado", 0) or 0
            categorias[desc]["saldo"] += row.get("saldo", 0) or 0

        # Ordena por orçado
        top_categorias = sorted(categorias.items(), key=lambda x: x[1]["orcado"], reverse=True)[:10]

        for i, (desc, valores) in enumerate(top_categorias, 1):
            print(f"{i:2d}. {desc[:50]}")
            print(f"    Orçado: R$ {valores['orcado']:,.2f}")
            print(f"    Realizado: R$ {valores['realizado']:,.2f}")
            print(f"    Saldo: R$ {valores['saldo']:,.2f}")
            print()

        # Calcula totais gerais
        for cat, vals in categorias.items():
            total_orcado += vals["orcado"]
            total_realizado += vals["realizado"]
            total_saldo += vals["saldo"]

        print("-" * 80)
        print("4. TOTAIS GERAIS:")
        print(f"   Total Orçado: R$ {total_orcado:,.2f}")
        print(f"   Total Realizado: R$ {total_realizado:,.2f}")
        print(f"   Total Saldo: R$ {total_saldo:,.2f}")
        print(f"   Percentual Realizado: {(total_realizado/total_orcado*100):.2f}%")

        # Verifica valores específicos da resposta da IA
        print("\n" + "=" * 80)
        print("5. VALIDACAO DOS VALORES DA IA:")
        print("-" * 80)

        # Serviço de Apoio (busca sem acentos)
        servico_apoio = categorias.get("SERVICO DE APOIO", {})
        print(f"Servico de Apoio:")
        print(f"  IA disse: Orcado R$ 4.999.881,08")
        print(f"  Banco:    Orcado R$ {servico_apoio.get('orcado', 0):,.2f}")
        match1 = "[OK]" if abs(servico_apoio.get('orcado', 0) - 4999881.08) < 1 else "[ERRO]"
        print(f"  Match: {match1}")
        print()

        # Remuneração (busca sem acentos)
        remuneracao = categorias.get("REMUNERACAO", {})
        print(f"Remuneracao:")
        print(f"  IA disse: Orcado R$ 1.147.237,60")
        print(f"  Banco:    Orcado R$ {remuneracao.get('orcado', 0):,.2f}")
        match2 = "[OK]" if abs(remuneracao.get('orcado', 0) - 1147237.60) < 1 else "[ERRO]"
        print(f"  Match: {match2}")
        print()

        # Almoxarifado
        almox = categorias.get("ALMOXARIFADO", {})
        print(f"Almoxarifado:")
        print(f"  IA disse: Orcado R$ 791.705,88")
        print(f"  Banco:    Orcado R$ {almox.get('orcado', 0):,.2f}")
        match3 = "[OK]" if abs(almox.get('orcado', 0) - 791705.88) < 1 else "[ERRO]"
        print(f"  Match: {match3}")
        print()

        # Total Geral
        print(f"Total Geral:")
        print(f"  IA disse: Orcado R$ 14.351.969,81")
        print(f"  Banco:    Orcado R$ {total_orcado:,.2f}")
        match4 = "[OK]" if abs(total_orcado - 14351969.81) < 1 else "[ERRO]"
        print(f"  Match: {match4}")

        # Exibe todas as categorias para debug
        print(f"\n\n6. DEBUG - TODAS AS CATEGORIAS NO BANCO:")
        print("-" * 80)
        for desc in sorted(categorias.keys()):
            print(f"  - '{desc}': R$ {categorias[desc]['orcado']:,.2f}")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()


if __name__ == "__main__":
    test_orcamento_jan2026()
