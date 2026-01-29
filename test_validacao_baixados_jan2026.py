"""
Valida a resposta da IA sobre contratos baixados EM janeiro 2026
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_validacao_baixados_jan2026():
    """Compara resposta da IA com dados reais"""
    print("=" * 80)
    print("VALIDACAO - RESPOSTA DA IA SOBRE CONTRATOS BAIXADOS EM JAN/2026")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Busca TODOS os contratos
        print("2. Buscando todos os contratos...")
        results = sql_client.execute_function("IA_Vendas", {})

        if not results:
            print("[AVISO] Nenhum registro encontrado")
            return

        print(f"[OK] {len(results)} registros encontrados\n")

        # Filtra contratos baixados EM janeiro 2026
        baixados_jan2026 = []
        for row in results:
            baixa = row.get("baixaReceber")
            if baixa and str(baixa).strip().startswith("202601"):
                baixados_jan2026.append({
                    "cliente": row.get("cliente", "N/A"),
                    "contrato": row.get("contrato", "N/A"),
                    "baixa": str(baixa).strip(),
                    "embarque": row.get("mesEmbarque", "N/A"),
                })

        # Agrupa por cliente
        por_cliente_banco = defaultdict(list)
        for item in baixados_jan2026:
            por_cliente_banco[item["cliente"]].append(item["contrato"])

        # Resposta da IA
        ia_respondeu = {
            "BERNHARD ROTHFOS GMB": ["500/25A", "547/25 "],
            "NESTRADE S.A.       ": ["375/25C"],
            "NESTLE ARARAS       ": ["093/25C", "094/25A", "094/25B"],
            "COFFEA IMPORTACAO, E": ["081/25A", "079/25D"],
            "NESTLE BRASIL LTDA. ": ["096/25A"],
            "J R COMERCIO E EXPOR": ["085/25D", "086/25A"],
            "CAFE FUNDADOR       ": ["582/25 ", "583/25 ", "584/25 "],
        }

        print("3. COMPARACAO:")
        print("-" * 80)

        print(f"\nIA mencionou: {len(ia_respondeu)} clientes")
        total_contratos_ia = sum(len(c) for c in ia_respondeu.values())
        print(f"Total de contratos mencionados: {total_contratos_ia}")

        print(f"\nBanco tem: {len(por_cliente_banco)} clientes")
        print(f"Total de contratos no banco: {len(baixados_jan2026)}")

        # Validação detalhada
        print("\n4. VALIDACAO DETALHADA:")
        print("-" * 80)

        clientes_corretos = 0
        contratos_corretos = 0
        contratos_incorretos = 0
        clientes_faltando = []

        for cliente_ia, contratos_ia in ia_respondeu.items():
            # Normaliza nome do cliente
            cliente_ia_norm = cliente_ia.strip()

            # Procura cliente no banco
            cliente_encontrado = None
            for cliente_banco in por_cliente_banco.keys():
                if cliente_ia_norm in cliente_banco or cliente_banco in cliente_ia_norm:
                    cliente_encontrado = cliente_banco
                    break

            if cliente_encontrado:
                clientes_corretos += 1
                contratos_banco = set(c.strip() for c in por_cliente_banco[cliente_encontrado])
                contratos_ia_set = set(c.strip() for c in contratos_ia)

                corretos = contratos_ia_set & contratos_banco
                errados = contratos_ia_set - contratos_banco
                faltando = contratos_banco - contratos_ia_set

                contratos_corretos += len(corretos)
                contratos_incorretos += len(errados)

                print(f"\n{cliente_ia_norm}:")
                print(f"  IA: {len(contratos_ia)} contratos")
                print(f"  Banco: {len(contratos_banco)} contratos")
                print(f"  Corretos: {len(corretos)}/{len(contratos_ia)}")

                if corretos == contratos_ia_set and len(faltando) == 0:
                    print(f"  [OK] 100% correto!")
                else:
                    if errados:
                        print(f"  [ERRO] Contratos incorretos: {sorted(errados)}")
                    if faltando:
                        print(f"  [AVISO] Faltou mencionar: {sorted(faltando)}")
            else:
                print(f"\n{cliente_ia_norm}: [ERRO] Cliente não encontrado!")

        # Verifica clientes que a IA não mencionou
        print("\n5. CLIENTES QUE A IA NAO MENCIONOU:")
        print("-" * 80)

        for cliente_banco in sorted(por_cliente_banco.keys()):
            encontrou = False
            for cliente_ia in ia_respondeu.keys():
                if cliente_ia.strip() in cliente_banco or cliente_banco in cliente_ia.strip():
                    encontrou = True
                    break
            if not encontrou:
                clientes_faltando.append(cliente_banco)
                contratos_faltando = por_cliente_banco[cliente_banco]
                print(f"\n{cliente_banco}:")
                print(f"  Contratos: {', '.join(contratos_faltando)}")

        # Resultado final
        print("\n6. RESULTADO FINAL:")
        print("-" * 80)

        taxa_acerto_contratos = (contratos_corretos / len(baixados_jan2026) * 100) if baixados_jan2026 else 0

        print(f"Contratos mencionados pela IA: {total_contratos_ia}")
        print(f"Contratos corretos: {contratos_corretos}")
        print(f"Contratos incorretos: {contratos_incorretos}")
        print(f"Total de contratos no banco: {len(baixados_jan2026)}")
        print(f"Taxa de acerto: {taxa_acerto_contratos:.1f}%")

        if clientes_faltando:
            print(f"\nClientes não mencionados: {len(clientes_faltando)}")
            total_contratos_faltando = sum(len(por_cliente_banco[c]) for c in clientes_faltando)
            print(f"Total de contratos faltando: {total_contratos_faltando}")

        if taxa_acerto_contratos == 100:
            print("\n[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif taxa_acerto_contratos >= 90:
            print(f"\n[MUITO BOM] Resposta da IA está {taxa_acerto_contratos:.1f}% correta")
        elif taxa_acerto_contratos >= 75:
            print(f"\n[BOM] Resposta da IA está {taxa_acerto_contratos:.1f}% correta")
        elif taxa_acerto_contratos >= 50:
            print(f"\n[PARCIAL] Resposta da IA está {taxa_acerto_contratos:.1f}% correta")
        else:
            print(f"\n[RUIM] Resposta da IA está apenas {taxa_acerto_contratos:.1f}% correta")

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
    test_validacao_baixados_jan2026()
