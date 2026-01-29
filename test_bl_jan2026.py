"""
Verifica contratos de janeiro 2026 que já têm número de BL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_bl_jan2026():
    """Lista contratos com número de BL em janeiro 2026"""
    print("=" * 80)
    print("VERIFICACAO - CONTRATOS COM BL EM JANEIRO 2026")
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

        # Separa contratos COM e SEM BL
        contratos_com_bl = []
        contratos_sem_bl = []

        for row in results:
            contrato = row.get("contrato", "N/A")
            cliente = row.get("cliente", "N/A")
            numero_bl = row.get("numeroBL")

            # Verifica se tem BL (não vazio, não None)
            if numero_bl and str(numero_bl).strip():
                contratos_com_bl.append({
                    "cliente": cliente,
                    "contrato": contrato,
                    "numeroBL": numero_bl
                })
            else:
                contratos_sem_bl.append({
                    "cliente": cliente,
                    "contrato": contrato
                })

        # Agrupa por cliente
        por_cliente = defaultdict(list)
        for item in contratos_com_bl:
            por_cliente[item["cliente"]].append(item["contrato"])

        print("3. CONTRATOS COM NUMERO DE BL:")
        print("-" * 80)

        if contratos_com_bl:
            for cliente in sorted(por_cliente.keys()):
                contratos = sorted(por_cliente[cliente])
                print(f"\n{cliente}:")
                for contrato in contratos:
                    print(f"  - {contrato}")

            print(f"\nTotal de contratos COM BL: {len(contratos_com_bl)}")
            print(f"Total de clientes: {len(por_cliente)}")
        else:
            print("Nenhum contrato com BL encontrado")

        # Comparação com resposta da IA
        print("\n4. COMPARACAO COM RESPOSTA DA IA:")
        print("-" * 80)

        ia_disse = {
            "BERNHARD ROTHFOS GMB": ["400/25A", "400/25B", "500/25A", "500/25B", "547/25", "548/25", "557/25", "556/25B", "580/25", "556/25C"],
            "THE FOLGER COFFEE": ["565/25A", "565/25B", "566/25A", "566/25B"],
            "JDE": ["256/25R", "256/25S", "544/25", "594/25"],
            "NESTRADE S.A.": ["378/25", "535/25", "536/25", "573/25", "375/25C", "375/25D", "379/25G", "379/25I"],
            "NESTLE ARARAS": ["093/25A", "093/25B", "093/25C", "094/25A", "094/25B", "002/26C", "002/26D", "002/26E", "002/26F"]
        }

        print("\nIA disse:")
        total_ia = 0
        for cliente, contratos in ia_disse.items():
            print(f"  {cliente}: {len(contratos)} contratos")
            total_ia += len(contratos)
        print(f"Total: {total_ia} contratos de {len(ia_disse)} clientes")

        print("\nBanco tem:")
        for cliente in sorted(por_cliente.keys()):
            print(f"  {cliente}: {len(por_cliente[cliente])} contratos")
        print(f"Total: {len(contratos_com_bl)} contratos de {len(por_cliente)} clientes")

        # Validação detalhada
        print("\n5. VALIDACAO DETALHADA:")
        print("-" * 80)

        validacoes = []

        # Verifica cada cliente que a IA mencionou
        for cliente_ia, contratos_ia in ia_disse.items():
            # Busca cliente similar no banco (pode ter variações no nome)
            cliente_banco = None
            for c in por_cliente.keys():
                if cliente_ia.upper() in c.upper() or c.upper() in cliente_ia.upper():
                    cliente_banco = c
                    break

            if cliente_banco:
                contratos_banco = set(por_cliente[cliente_banco])
                contratos_ia_set = set(contratos_ia)

                corretos = contratos_ia_set & contratos_banco
                faltando = contratos_banco - contratos_ia_set
                extras = contratos_ia_set - contratos_banco

                print(f"\n{cliente_ia}:")
                print(f"  IA mencionou: {len(contratos_ia)} contratos")
                print(f"  Banco tem: {len(contratos_banco)} contratos")
                print(f"  Corretos: {len(corretos)}/{len(contratos_ia)}")

                if faltando:
                    print(f"  [AVISO] Contratos que a IA NAO mencionou ({len(faltando)}): {sorted(faltando)}")

                if extras:
                    print(f"  [ERRO] Contratos que a IA mencionou mas NAO existem ({len(extras)}): {sorted(extras)}")

                validacoes.append(len(extras) == 0 and len(faltando) == 0)
            else:
                print(f"\n{cliente_ia}: [ERRO] Cliente não encontrado no banco!")
                validacoes.append(False)

        # Verifica se há clientes no banco que a IA não mencionou
        clientes_banco = set(por_cliente.keys())
        clientes_ia_normalizados = set()
        for c_ia in ia_disse.keys():
            for c_banco in clientes_banco:
                if c_ia.upper() in c_banco.upper() or c_banco.upper() in c_ia.upper():
                    clientes_ia_normalizados.add(c_banco)

        clientes_faltando = clientes_banco - clientes_ia_normalizados
        if clientes_faltando:
            print(f"\n[AVISO] Clientes com BL que a IA NAO mencionou ({len(clientes_faltando)}):")
            for cliente in sorted(clientes_faltando):
                print(f"  - {cliente}: {len(por_cliente[cliente])} contratos")
                print(f"    Contratos: {sorted(por_cliente[cliente])}")

        # Mostra alguns contratos SEM BL para contexto
        print("\n6. CONTRATOS SEM BL (primeiros 10):")
        print("-" * 80)
        for i, item in enumerate(contratos_sem_bl[:10], 1):
            print(f"  {i}. {item['cliente']} - {item['contrato']}")

        if len(contratos_sem_bl) > 10:
            print(f"  ... e mais {len(contratos_sem_bl) - 10} contratos sem BL")

        # Resultado final
        print("\n7. RESULTADO FINAL:")
        print("-" * 80)

        if all(validacoes) and not clientes_faltando:
            print("[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif not clientes_faltando and sum(validacoes) >= len(validacoes) * 0.9:
            print(f"[PARCIAL] Resposta da IA esta {sum(validacoes)}/{len(validacoes)} correta")
        else:
            print(f"[AVISO] Resposta pode estar incompleta ou com divergências")
            if clientes_faltando:
                print(f"  - {len(clientes_faltando)} cliente(s) com BL não foram mencionados")

        print(f"\nEstatísticas:")
        print(f"  - Total de contratos janeiro 2026: {len(results)}")
        print(f"  - Contratos COM BL: {len(contratos_com_bl)} ({len(contratos_com_bl)/len(results)*100:.1f}%)")
        print(f"  - Contratos SEM BL: {len(contratos_sem_bl)} ({len(contratos_sem_bl)/len(results)*100:.1f}%)")

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
    test_bl_jan2026()
