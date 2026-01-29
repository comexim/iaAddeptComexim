"""
Validacao FINAL: Contratos FREY A/S baixados
Campo correto: baixaReceber (nao dataBaixa!)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_frey_final():
    """Validacao final FREY A/S"""
    print("=" * 80)
    print("VALIDACAO FINAL - FREY A/S: Contratos baixados")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Quantos contratos do cliente FREY A/S em novembro e")
        print("          dezembro de 2025 ja foram baixados financeiramente?")
        print("          Liste os numeros dos contratos.")
        print("")
        print("Resposta IA:")
        print("  'Em novembro e dezembro de 2025, dois contratos do cliente FREY A/S")
        print("   ja foram baixados financeiramente.'")
        print("  Contratos: 530/25 e 531/25")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando contratos FREY A/S com embarque nov/dez 2025")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        # Filtra FREY com embarque nov/dez 2025
        frey_novdez = []
        for r in result:
            cliente = r.get("cliente", "").strip().upper()
            mes_embarque = r.get("mesEmbarque", "").strip()
            if "FREY" in cliente and mes_embarque in ["2025/11", "2025/12"]:
                frey_novdez.append(r)

        print(f"Contratos FREY com embarque nov/dez 2025: {len(frey_novdez)}")

        print("\n4. Detalhes de cada contrato:")
        print("=" * 80)

        contratos_info = []
        for r in frey_novdez:
            contrato = r.get("contrato", "").strip()
            mes_embarque = r.get("mesEmbarque", "").strip()
            baixa_receber = r.get("baixaReceber", "")  # CAMPO CORRETO!
            cliente = r.get("cliente", "").strip()

            # Verifica se foi baixado (campo correto: baixaReceber)
            foi_baixado = bool(baixa_receber and str(baixa_receber).strip() and str(baixa_receber).strip() != "None")

            info = {
                "contrato": contrato,
                "mes_embarque": mes_embarque,
                "baixa_receber": str(baixa_receber).strip() if foi_baixado else None,
                "foi_baixado": foi_baixado,
                "cliente": cliente
            }
            contratos_info.append(info)

            status = "BAIXADO" if foi_baixado else "NAO BAIXADO"
            baixa_str = str(baixa_receber).strip() if foi_baixado else "-"

            print(f"\nContrato: {contrato}")
            print(f"  Cliente: {cliente}")
            print(f"  Mes Embarque: {mes_embarque}")
            print(f"  Baixa Receber: {baixa_str}")
            print(f"  Status: {status}")

            # Mostra quando foi baixado
            if foi_baixado and len(baixa_str) == 8:
                dia = baixa_str[6:8]
                mes = baixa_str[4:6]
                ano = baixa_str[:4]
                print(f"  Data Baixa: {dia}/{mes}/{ano}")

        # Filtra apenas os baixados
        baixados = [c for c in contratos_info if c["foi_baixado"]]

        print("\n5. CONTRATOS QUE JA FORAM BAIXADOS:")
        print("=" * 80)
        print(f"Total: {len(baixados)}")

        if baixados:
            for c in baixados:
                print(f"  - {c['contrato']}")
        else:
            print("  [!] Nenhum contrato foi baixado")

        print("\n6. VERIFICACAO:")
        print("=" * 80)

        contratos_baixados_lista = sorted([c["contrato"] for c in baixados])
        ia_disse_contratos = sorted(['530/25', '531/25'])

        print(f"\nIA disse:")
        print(f"  - Quantidade: 2 contratos")
        print(f"  - Contratos: 530/25, 531/25")

        print(f"\nBanco tem:")
        print(f"  - Quantidade: {len(baixados)} contratos")
        print(f"  - Contratos: {', '.join(contratos_baixados_lista) if contratos_baixados_lista else 'nenhum'}")

        # Verifica quantidade
        if len(baixados) == 2:
            print("\n[OK] Quantidade correta: 2 contratos")
            qtd_correta = True
        else:
            print(f"\n[X] Quantidade incorreta: IA disse 2, banco tem {len(baixados)}")
            qtd_correta = False

        # Verifica contratos
        if contratos_baixados_lista == ia_disse_contratos:
            print("[OK] Contratos corretos: 530/25 e 531/25")
            contratos_corretos = True
        else:
            print(f"[X] Contratos incorretos")
            contratos_corretos = False

        # Verifica QUANDO foram baixados
        print("\n7. ANALISE CRITICA - QUANDO FORAM BAIXADOS?")
        print("=" * 80)

        if baixados:
            print("\nDatas de baixa:")
            todos_em_novdez = True
            for c in baixados:
                baixa_str = c["baixa_receber"]
                if len(baixa_str) == 8:
                    dia = baixa_str[6:8]
                    mes = baixa_str[4:6]
                    ano = baixa_str[:4]
                    ano_mes = baixa_str[:6]  # YYYYMM

                    print(f"  - {c['contrato']}: {dia}/{mes}/{ano}")

                    if ano_mes not in ["202511", "202512"]:
                        todos_em_novdez = False
                        print(f"    [!] Baixado em {mes}/{ano}, NAO em nov/dez 2025!")

            if not todos_em_novdez:
                print("\n[X] PROBLEMA: A IA disse 'Em novembro e dezembro de 2025'")
                print("    mas os contratos foram baixados FORA desse periodo!")
                precisao_correta = False
            else:
                print("\n[OK] Contratos foram realmente baixados em nov/dez 2025")
                precisao_correta = True
        else:
            precisao_correta = False

        print("\n8. RESULTADO FINAL:")
        print("=" * 80)

        if qtd_correta and contratos_corretos:
            if precisao_correta:
                print("\n" + "=" * 80)
                print("[OK][OK][OK] RESPOSTA DA IA ESTA 100% CORRETA! [OK][OK][OK]")
                print("=" * 80)
            else:
                print("\n" + "=" * 80)
                print("[OK][~][X] RESPOSTA DA IA ESTA PARCIALMENTE CORRETA [OK][~][X]")
                print("=" * 80)

            print("\nCampos corretos:")
            print("  [OK] Quantidade: 2 contratos")
            print("  [OK] Contratos: 530/25 e 531/25")

            if not precisao_correta:
                print("\nProblema encontrado:")
                print("  [X] A IA disse que os contratos foram baixados 'em novembro e")
                print("      dezembro de 2025', mas eles foram baixados em JANEIRO 2026!")
                print("\nResposta mais precisa seria:")
                print("  'Os 2 contratos do FREY A/S com embarque em dezembro 2025")
                print("   (530/25 e 531/25) ja foram baixados financeiramente, em 08/01/2026.'")
        else:
            print("\n" + "=" * 80)
            print("[X][X][X] RESPOSTA DA IA ESTA INCORRETA! [X][X][X]")
            print("=" * 80)
            print("\nErros:")
            if not qtd_correta:
                print(f"  [X] Quantidade: IA disse 2, banco tem {len(baixados)}")
            if not contratos_corretos:
                print(f"  [X] Contratos: IA disse {ia_disse_contratos}, banco tem {contratos_baixados_lista}")

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
    test_frey_final()
