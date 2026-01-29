"""
Verifica todas as peneiras únicas em janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_peneiras_jan2026():
    """Lista todas as peneiras únicas de janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - PENEIRAS JANEIRO 2026")
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

        # Coleta todos os valores de peneiras
        peneiras_valores = {
            "peneiraMTGB": set(),
            "peneiraGrauda": set(),
            "peneiraGrinder": set()
        }

        contratos_por_peneira = {
            "peneiraMTGB": {},
            "peneiraGrauda": {},
            "peneiraGrinder": {}
        }

        for row in results:
            contrato = row.get("contrato", "N/A")

            # Peneira MTGB
            mtgb = row.get("peneiraMTGB")
            if mtgb is not None and mtgb != 0:
                mtgb_val = float(mtgb)
                peneiras_valores["peneiraMTGB"].add(mtgb_val)
                if mtgb_val not in contratos_por_peneira["peneiraMTGB"]:
                    contratos_por_peneira["peneiraMTGB"][mtgb_val] = []
                contratos_por_peneira["peneiraMTGB"][mtgb_val].append(contrato)

            # Peneira Grauda
            grauda = row.get("peneiraGrauda")
            if grauda is not None and grauda != 0:
                grauda_val = float(grauda)
                peneiras_valores["peneiraGrauda"].add(grauda_val)
                if grauda_val not in contratos_por_peneira["peneiraGrauda"]:
                    contratos_por_peneira["peneiraGrauda"][grauda_val] = []
                contratos_por_peneira["peneiraGrauda"][grauda_val].append(contrato)

            # Peneira Grinder
            grinder = row.get("peneiraGrinder")
            if grinder is not None and grinder != 0:
                grinder_val = float(grinder)
                peneiras_valores["peneiraGrinder"].add(grinder_val)
                if grinder_val not in contratos_por_peneira["peneiraGrinder"]:
                    contratos_por_peneira["peneiraGrinder"][grinder_val] = []
                contratos_por_peneira["peneiraGrinder"][grinder_val].append(contrato)

        # Mostra peneiras por tipo
        print("3. PENEIRAS ENCONTRADAS POR TIPO:")
        print("-" * 80)

        for tipo, valores in peneiras_valores.items():
            if valores:
                valores_ordenados = sorted(list(valores))
                print(f"\n{tipo}:")
                for valor in valores_ordenados:
                    num_contratos = len(contratos_por_peneira[tipo][valor])
                    print(f"  - Peneira {int(valor):2d}: {num_contratos} contratos")
            else:
                print(f"\n{tipo}: Nenhuma encontrada")

        # Cria conjunto único de todos os tamanhos de peneiras
        todas_peneiras = set()
        for valores in peneiras_valores.values():
            todas_peneiras.update(valores)

        todas_peneiras_ordenadas = sorted(list(todas_peneiras))

        print("\n4. TODAS AS PENEIRAS UNICAS (CONSOLIDADO):")
        print("-" * 80)
        for peneira in todas_peneiras_ordenadas:
            print(f"  - Peneira {int(peneira)}")

        print(f"\nTotal de tamanhos de peneira únicos: {len(todas_peneiras_ordenadas)}")

        # Comparação com resposta da IA
        print("\n5. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = [13, 14, 15, 16, 17, 18]

        print("IA disse:")
        for p in ia_disse:
            print(f"  - Peneira {p}")

        print(f"\nTotal mencionado pela IA: {len(ia_disse)}")

        print("\nBanco tem:")
        for p in todas_peneiras_ordenadas:
            print(f"  - Peneira {int(p)}")

        print(f"\nTotal no banco: {len(todas_peneiras_ordenadas)}")

        # Validação
        print("\n6. VALIDACAO:")
        print("-" * 80)

        ia_set = set(ia_disse)
        banco_set = set(int(p) for p in todas_peneiras_ordenadas)

        corretos = ia_set & banco_set
        faltando = banco_set - ia_set
        extras = ia_set - banco_set

        print(f"Peneiras corretas: {len(corretos)}/{len(ia_set)}")
        if corretos:
            print(f"  Corretos: {sorted(corretos)}")

        if faltando:
            print(f"\nPeneiras que a IA NAO mencionou: {len(faltando)}")
            print(f"  Faltando: {sorted(faltando)}")

        if extras:
            print(f"\nPeneiras que a IA mencionou mas NAO existem: {len(extras)}")
            print(f"  Extras: {sorted(extras)}")

        # Resultado final
        print("\n7. RESULTADO FINAL:")
        print("-" * 80)

        if not faltando and not extras:
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif not extras:
            print(f"[PARCIAL] IA mencionou {len(corretos)} peneiras corretas, mas faltou {len(faltando)}")
        else:
            print(f"[ERRO] IA mencionou {len(extras)} peneira(s) que nao existem")

        taxa_acerto = (len(corretos) / len(ia_disse) * 100) if ia_disse else 0
        print(f"Taxa de acerto: {taxa_acerto:.1f}%")

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
    test_peneiras_jan2026()
