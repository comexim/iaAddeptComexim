"""
Valida a NOVA resposta da IA sobre amostras pendentes
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict

def test_nova_resposta():
    """Compara nova resposta da IA com dados reais"""
    print("=" * 80)
    print("VALIDACAO - NOVA RESPOSTA DA IA SOBRE AMOSTRAS PENDENTES")
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

        # Identifica contratos que enviaram amostra mas não aprovaram
        pendentes_banco = []
        for row in results:
            envio = row.get("envioAmostra")
            aprovacao = row.get("aprovAmostra")
            enviou = envio and str(envio).strip()
            aprovou = aprovacao and str(aprovacao).strip()

            if enviou and not aprovou:
                pendentes_banco.append({
                    "cliente": row.get("cliente", "N/A"),
                    "contrato": row.get("contrato", "N/A"),
                })

        # Agrupa por cliente
        por_cliente_banco = defaultdict(list)
        for item in pendentes_banco:
            por_cliente_banco[item["cliente"]].append(item["contrato"])

        # Resposta da IA (nova)
        ia_respondeu = {
            "THE FOLGER COFFEE   ": ["565/25A", "565/25B", "566/25A", "566/25B"],
            "LOS CINCO HISPANOS S": ["590/25 ", "019/26 ", "021/26 "],
            "IMPORTADORA REAL    ": ["010/26 ", "013/26 "],
            "CAFES LA VIRGINIA   ": ["577/25 ", "578/25 "],
            "CAFE FUNDADOR       ": ["582/25 ", "583/25 ", "584/25 "],
            "BROOKS CO. LTD.     ": ["526/25 "],
            "MIORI               ": ["514/25 "],
            "ATLANTIC USA IN     ": ["589/25 "],
            "IRAKLIS ROUPAS LTDA ": ["001/26 "],
        }

        print("3. COMPARACAO:")
        print("-" * 80)

        print(f"\nIA mencionou: {len(ia_respondeu)} clientes")
        total_contratos_ia = sum(len(c) for c in ia_respondeu.values())
        print(f"Total de contratos mencionados: {total_contratos_ia}")

        print(f"\nBanco tem: {len(por_cliente_banco)} clientes")
        print(f"Total de contratos no banco: {len(pendentes_banco)}")

        # Validação detalhada
        print("\n4. VALIDACAO DETALHADA:")
        print("-" * 80)

        clientes_corretos = 0
        contratos_corretos = 0
        contratos_incorretos = 0
        clientes_faltando = []

        for cliente_ia, contratos_ia in ia_respondeu.items():
            # Normaliza nome do cliente (remove espaços extras)
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

                if errados:
                    print(f"  [ERRO] Contratos incorretos: {sorted(errados)}")
                if faltando:
                    print(f"  [AVISO] Faltou mencionar: {sorted(faltando)}")
            else:
                print(f"\n{cliente_ia_norm}: [ERRO] Cliente não encontrado!")

        # Verifica clientes que a IA não mencionou
        for cliente_banco in por_cliente_banco.keys():
            encontrou = False
            for cliente_ia in ia_respondeu.keys():
                if cliente_ia.strip() in cliente_banco or cliente_banco in cliente_ia.strip():
                    encontrou = True
                    break
            if not encontrou:
                clientes_faltando.append(cliente_banco)
                contratos_faltando = por_cliente_banco[cliente_banco]
                print(f"\n[FALTOU] {cliente_banco}:")
                print(f"  Contratos: {', '.join(contratos_faltando)}")

        # Resultado final
        print("\n5. RESULTADO FINAL:")
        print("-" * 80)

        taxa_acerto_clientes = (clientes_corretos / len(por_cliente_banco) * 100) if por_cliente_banco else 0
        taxa_acerto_contratos = (contratos_corretos / len(pendentes_banco) * 100) if pendentes_banco else 0

        print(f"Clientes: {clientes_corretos}/{len(por_cliente_banco)} corretos ({taxa_acerto_clientes:.1f}%)")
        print(f"Contratos: {contratos_corretos}/{len(pendentes_banco)} corretos ({taxa_acerto_contratos:.1f}%)")

        if clientes_faltando:
            print(f"\nClientes não mencionados: {len(clientes_faltando)}")
            for c in clientes_faltando:
                print(f"  - {c}")

        if contratos_incorretos > 0:
            print(f"\n[AVISO] {contratos_incorretos} contrato(s) mencionados incorretamente")

        if taxa_acerto_contratos == 100:
            print("\n[OK] RESPOSTA DA IA ESTA 100% CORRETA!")
        elif taxa_acerto_contratos >= 90:
            print(f"\n[MUITO BOM] Resposta da IA esta {taxa_acerto_contratos:.1f}% correta")
        elif taxa_acerto_contratos >= 75:
            print(f"\n[BOM] Resposta da IA esta {taxa_acerto_contratos:.1f}% correta")
        else:
            print(f"\n[PARCIAL] Resposta da IA esta {taxa_acerto_contratos:.1f}% correta")

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
    test_nova_resposta()
