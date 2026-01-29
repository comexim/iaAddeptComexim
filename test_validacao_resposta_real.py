"""
Valida a resposta REAL da IA contra o banco de dados
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from collections import defaultdict
import re

# Resposta REAL da IA
resposta_ia = """
- UCC-COFFEE SERVICES: 5 contratos (234/25, 133/25, 165/25, 384/25, 167/25)
- VOLCAFE: 2 contratos (523/25A, 546/25B)
- NESTRADE S.A.: 4 contratos (375/25C, 253/25, 279/25, 280/25)
- JULIUS MEINL: 1 contrato (193/25)
- MARKUS KAFFEE: 1 contrato (013/25R)
- MEIRA (MZB GROUP): 1 contrato (019/25)
- I.M. FRELLSEN K/S: 4 contratos (562/25, 560/25, 229/25, 499/25)
- FREY A/S: 2 contratos (531/25, 530/25)
- STRAUSS COMMODITIES: 1 contrato (487/25)
- GIMOKA: 1 contrato (299/25)
- COFFEA IMPORTACAO, E: 2 contratos (079/25D, 081/25A)
- NESTLE BRASIL LTDA: 2 contratos (095/25, 090/25)
- JAMES FINLAY (ME) DM: 1 contrato (543/25)
- CAFE FUNDADOR: 3 contratos (582/25, 584/25, 583/25)
- NESTLE ARARAS: 6 contratos (092/25, 094/25B, 094/25A, 093/25C, 045/25B, 091/25)
- UPSTREAM COFFEE IMP: 2 contratos (465/25, 466/25)
- J R COMERCIO E EXPOR: 2 contratos (085/25D, 086/25A)
- NESTLE BRASIL LTDA.: 1 contrato (096/25A)
- JDE: 1 contrato (175/25R)
- LOS CINCO HISPANOS S: 3 contratos (441/25, 442/25, 506/25)
- SWISS WATER: 1 contrato (511/25)
- EFICO NV: 5 contratos (491/25, 468/25, 492/25, 528/25, 490/25)
- COMEXIM EUROPE GMBH.: 7 contratos (106/25, 246/25, 486/25, 505/25, 362/25, 481/25, 504/25)
- BERNHARD ROTHFOS GMB: 5 contratos (453/25B, 453/25A, 547/25, 500/25A, 347/25)
- AHOLD COFFEE: 4 contratos (030/25, 038/25, 033/25, 037/25)
"""

def test_validacao_resposta_real():
    """Valida resposta real da IA contra o banco"""
    print("=" * 80)
    print("VALIDACAO - RESPOSTA REAL DA IA")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return

        print("[OK] Conectado\n")

        # Busca TODOS os contratos baixados em jan/2026
        print("2. Buscando contratos baixados em jan/2026 no banco...")
        results = sql_client.execute_function("IA_Vendas", {})

        baixados_jan2026_banco = {}
        for row in results:
            baixa = row.get("baixaReceber")
            if baixa and str(baixa).strip().startswith("202601"):
                cliente = row.get("cliente", "").strip()
                contrato = row.get("contrato", "").strip()

                if cliente not in baixados_jan2026_banco:
                    baixados_jan2026_banco[cliente] = []
                baixados_jan2026_banco[cliente].append(contrato)

        print(f"[OK] {sum(len(v) for v in baixados_jan2026_banco.values())} contratos de {len(baixados_jan2026_banco)} clientes\n")

        # Parse resposta da IA
        print("3. Parseando resposta da IA...")
        contratos_ia = {}
        for line in resposta_ia.strip().split('\n'):
            if not line.strip():
                continue

            # Extrai cliente
            match = re.match(r'^-\s+(.+?):\s+\d+\s+contrato', line)
            if not match:
                continue

            cliente = match.group(1).strip()

            # Extrai contratos entre parênteses
            contratos_match = re.search(r'\((.+)\)', line)
            if contratos_match:
                contratos_str = contratos_match.group(1)
                contratos = [c.strip() for c in contratos_str.split(',')]
                contratos_ia[cliente] = contratos

        print(f"[OK] {sum(len(v) for v in contratos_ia.values())} contratos de {len(contratos_ia)} clientes\n")

        # Validação
        print("4. VALIDACAO DETALHADA:")
        print("-" * 80)

        corretos = 0
        incorretos = 0
        faltando_clientes = []

        for cliente_ia, contratos_ia_list in sorted(contratos_ia.items()):
            # Normaliza nome do cliente (remove espaços extras)
            cliente_normalizado = ' '.join(cliente_ia.split())

            # Procura cliente no banco (permite match parcial)
            contratos_banco = None
            for cliente_banco, contratos_banco_list in baixados_jan2026_banco.items():
                cliente_banco_normalizado = ' '.join(cliente_banco.split())
                if cliente_banco_normalizado.startswith(cliente_normalizado) or cliente_normalizado.startswith(cliente_banco_normalizado):
                    contratos_banco = contratos_banco_list
                    break

            if contratos_banco is None:
                print(f"\n[ERRO] {cliente_ia}:")
                print(f"   Cliente NAO ENCONTRADO no banco!")
                incorretos += len(contratos_ia_list)
                continue

            # Normaliza contratos (remove espaços)
            contratos_ia_norm = [c.strip() for c in contratos_ia_list]
            contratos_banco_norm = [c.strip() for c in contratos_banco]

            # Verifica cada contrato
            corretos_cliente = 0
            incorretos_cliente = 0

            for c in contratos_ia_norm:
                if c in contratos_banco_norm:
                    corretos_cliente += 1
                else:
                    incorretos_cliente += 1

            corretos += corretos_cliente
            incorretos += incorretos_cliente

            if incorretos_cliente == 0:
                print(f"\n[OK] {cliente_ia}: {corretos_cliente}/{len(contratos_ia_norm)} corretos (100%)")
            else:
                print(f"\n[AVISO] {cliente_ia}: {corretos_cliente}/{len(contratos_ia_norm)} corretos ({corretos_cliente/len(contratos_ia_norm)*100:.0f}%)")
                if incorretos_cliente > 0:
                    incorretos_na_ia = [c for c in contratos_ia_norm if c not in contratos_banco_norm]
                    print(f"   Incorretos: {', '.join(incorretos_na_ia)}")

        # Verifica clientes que faltaram
        print("\n\n5. CLIENTES QUE FALTARAM NA RESPOSTA:")
        print("-" * 80)

        for cliente_banco, contratos_banco in sorted(baixados_jan2026_banco.items()):
            cliente_banco_normalizado = ' '.join(cliente_banco.split())

            encontrado = False
            for cliente_ia in contratos_ia.keys():
                cliente_ia_normalizado = ' '.join(cliente_ia.split())
                if cliente_banco_normalizado.startswith(cliente_ia_normalizado) or cliente_ia_normalizado.startswith(cliente_banco_normalizado):
                    encontrado = True
                    break

            if not encontrado:
                print(f"\n[FALTOU] {cliente_banco}: {len(contratos_banco)} contrato(s)")
                print(f"   {', '.join(contratos_banco[:10])}")
                faltando_clientes.append(cliente_banco)

        # Resultado final
        print("\n\n6. RESULTADO FINAL:")
        print("=" * 80)

        total_banco = sum(len(v) for v in baixados_jan2026_banco.values())
        total_ia = sum(len(v) for v in contratos_ia.values())

        print(f"Total de contratos no banco: {total_banco}")
        print(f"Total de contratos na IA: {total_ia}")
        print(f"Contratos corretos: {corretos}")
        print(f"Contratos incorretos: {incorretos}")
        print(f"Taxa de acerto: {corretos/total_banco*100:.1f}%")
        print(f"Clientes faltando: {len(faltando_clientes)}")

        if corretos == total_banco and incorretos == 0:
            print("\n[PERFEITO] Resposta 100% correta!")
        elif corretos/total_banco >= 0.9:
            print("\n[EXCELENTE] Resposta mais de 90% correta!")
        elif corretos/total_banco >= 0.75:
            print("\n[BOM] Resposta mais de 75% correta!")
        else:
            print("\n[RUIM] Resposta precisa melhorar")

        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_validacao_resposta_real()
