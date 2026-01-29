"""
Verifica médias das peneiras em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_peneiras_media_jan2026():
    """Calcula médias das peneiras de janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - MEDIAS DAS PENEIRAS JANEIRO 2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Consulta vendas de janeiro 2026
        print("2. Consultando vendas de janeiro 2026...")
        filters = {"mesEmbarque": "2026/01"}
        results = sql_client.execute_function("IA_Vendas", filters)

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Coleta valores de peneiras para calcular médias
        mtgb_values = []
        grauda_values = []
        grinder_values = []

        for row in results:
            # Peneira MTGB
            mtgb = row.get("peneiraMTGB")
            if mtgb is not None:
                mtgb_values.append(float(mtgb))

            # Peneira Grauda
            grauda = row.get("peneiraGrauda")
            if grauda is not None:
                grauda_values.append(float(grauda))

            # Peneira Grinder
            grinder = row.get("peneiraGrinder")
            if grinder is not None:
                grinder_values.append(float(grinder))

        # Calcula médias
        print("3. CALCULOS DE MEDIAS:")
        print("-" * 80)

        # MTGB
        if mtgb_values:
            # Filtra apenas valores não-zero para ver a distribuição
            mtgb_non_zero = [v for v in mtgb_values if v != 0]
            media_mtgb = sum(mtgb_values) / len(mtgb_values)
            media_mtgb_non_zero = sum(mtgb_non_zero) / len(mtgb_non_zero) if mtgb_non_zero else 0

            print(f"MTGB:")
            print(f"  Total de valores: {len(mtgb_values)}")
            print(f"  Valores nao-zero: {len(mtgb_non_zero)}")
            print(f"  Valores zero: {len(mtgb_values) - len(mtgb_non_zero)}")
            print(f"  Media (incluindo zeros): {media_mtgb:.1f}")
            print(f"  Media (apenas nao-zero): {media_mtgb_non_zero:.1f}")
            print(f"  Valores unicos: {sorted(set(mtgb_values))}")
        else:
            print("MTGB: Nenhum valor encontrado")
            media_mtgb = 0

        # Grauda
        print()
        if grauda_values:
            grauda_non_zero = [v for v in grauda_values if v != 0]
            media_grauda = sum(grauda_values) / len(grauda_values)
            media_grauda_non_zero = sum(grauda_non_zero) / len(grauda_non_zero) if grauda_non_zero else 0

            print(f"Grauda:")
            print(f"  Total de valores: {len(grauda_values)}")
            print(f"  Valores nao-zero: {len(grauda_non_zero)}")
            print(f"  Valores zero: {len(grauda_values) - len(grauda_non_zero)}")
            print(f"  Media (incluindo zeros): {media_grauda:.1f}")
            print(f"  Media (apenas nao-zero): {media_grauda_non_zero:.1f}")
            print(f"  Valores unicos: {sorted(set(grauda_values))}")
        else:
            print("Grauda: Nenhum valor encontrado")
            media_grauda = 0

        # Grinder
        print()
        if grinder_values:
            grinder_non_zero = [v for v in grinder_values if v != 0]
            media_grinder = sum(grinder_values) / len(grinder_values)
            media_grinder_non_zero = sum(grinder_non_zero) / len(grinder_non_zero) if grinder_non_zero else 0

            print(f"Grinder:")
            print(f"  Total de valores: {len(grinder_values)}")
            print(f"  Valores nao-zero: {len(grinder_non_zero)}")
            print(f"  Valores zero: {len(grinder_values) - len(grinder_non_zero)}")
            print(f"  Media (incluindo zeros): {media_grinder:.1f}")
            print(f"  Media (apenas nao-zero): {media_grinder_non_zero:.1f}")
            print(f"  Valores unicos: {sorted(set(grinder_values))}")
        else:
            print("Grinder: Nenhum valor encontrado")
            media_grinder = 0

        # Comparação com resposta da IA
        print("\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "mtgb": 100.0,
            "grauda": 0.0,
            "grinder": 0.0
        }

        print("IA disse:")
        print(f"  MTGB Media: {ia_disse['mtgb']:.1f}")
        print(f"  Grauda Media: {ia_disse['grauda']:.1f}")
        print(f"  Grinder Media: {ia_disse['grinder']:.1f}")

        print("\nBanco tem (incluindo zeros):")
        print(f"  MTGB Media: {media_mtgb:.1f}")
        print(f"  Grauda Media: {media_grauda:.1f}")
        print(f"  Grinder Media: {media_grinder:.1f}")

        # Validação
        print("\n5. VALIDACAO:")
        print("-" * 80)

        validacoes = []

        # MTGB
        diff_mtgb = abs(media_mtgb - ia_disse['mtgb'])
        if diff_mtgb < 0.1:
            print(f"[OK] MTGB: diferenca {diff_mtgb:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] MTGB: IA disse {ia_disse['mtgb']:.1f}, banco tem {media_mtgb:.1f}")
            validacoes.append(False)

        # Grauda
        diff_grauda = abs(media_grauda - ia_disse['grauda'])
        if diff_grauda < 0.1:
            print(f"[OK] Grauda: diferenca {diff_grauda:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Grauda: IA disse {ia_disse['grauda']:.1f}, banco tem {media_grauda:.1f}")
            validacoes.append(False)

        # Grinder
        diff_grinder = abs(media_grinder - ia_disse['grinder'])
        if diff_grinder < 0.1:
            print(f"[OK] Grinder: diferenca {diff_grinder:.2f}")
            validacoes.append(True)
        else:
            print(f"[ERRO] Grinder: IA disse {ia_disse['grinder']:.1f}, banco tem {media_grinder:.1f}")
            validacoes.append(False)

        # Resultado final
        print("\n6. RESULTADO FINAL:")
        print("-" * 80)

        if all(validacoes):
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        else:
            print(f"[PARCIAL] Resposta da IA: {sum(validacoes)}/3 correto")
            print("\nNOTA: A IA agora esta usando os campos corretos (nao mais extrai de descricoes)!")

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
    test_peneiras_media_jan2026()
