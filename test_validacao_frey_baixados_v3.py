"""
Valida: Contratos do FREY A/S baixados - interpretacao completa
Pergunta: "Quantos contratos do cliente FREY A/S em novembro e dezembro de 2025
          ja foram baixados financeiramente?"

INTERPRETACAO MAIS PROVAVEL:
"Contratos [com embarque] em novembro e dezembro de 2025 que JA foram baixados [ate hoje]"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_frey_completo():
    """Validacao completa FREY A/S"""
    print("=" * 80)
    print("VALIDACAO COMPLETA - FREY A/S: Contratos baixados")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Quantos contratos do cliente FREY A/S em novembro e")
        print("          dezembro de 2025 ja foram baixados financeiramente?")
        print("          Liste os numeros dos contratos.")
        print("")
        print("Resposta IA:")
        print("  Em novembro e dezembro de 2025, dois contratos do cliente FREY A/S")
        print("  ja foram baixados financeiramente.")
        print("  Contratos: 530/25 e 531/25")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando contratos FREY A/S")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        # Filtra FREY
        frey_todos = []
        for r in result:
            cliente = r.get("cliente", "").strip().upper()
            if "FREY" in cliente:
                frey_todos.append(r)

        print(f"Total de contratos FREY: {len(frey_todos)}")

        # Filtra por embarque nov/dez 2025
        frey_novdez = []
        for r in frey_todos:
            mes_embarque = r.get("mesEmbarque", "").strip()
            if mes_embarque in ["2025/11", "2025/12"]:
                frey_novdez.append(r)

        print(f"Contratos FREY com embarque nov/dez 2025: {len(frey_novdez)}")

        print("\n4. Detalhes dos contratos nov/dez 2025:")
        print("=" * 80)

        contratos_info = []
        for r in frey_novdez:
            contrato = r.get("contrato", "").strip()
            mes_embarque = r.get("mesEmbarque", "").strip()
            data_baixa = r.get("dataBaixa", "")
            cliente = r.get("cliente", "").strip()

            # Verifica se foi baixado
            foi_baixado = bool(data_baixa and str(data_baixa).strip() and str(data_baixa).strip() != "None")

            info = {
                "contrato": contrato,
                "mes_embarque": mes_embarque,
                "data_baixa": str(data_baixa).strip() if foi_baixado else None,
                "foi_baixado": foi_baixado,
                "cliente": cliente
            }
            contratos_info.append(info)

            status = "BAIXADO" if foi_baixado else "NAO BAIXADO"
            baixa_str = str(data_baixa).strip() if foi_baixado else "-"
            print(f"\nContrato: {contrato}")
            print(f"  Cliente: {cliente}")
            print(f"  Mes Embarque: {mes_embarque}")
            print(f"  Data Baixa: {baixa_str}")
            print(f"  Status: {status}")

        # Filtra apenas os baixados
        baixados = [c for c in contratos_info if c["foi_baixado"]]

        print("\n5. CONTRATOS QUE JA FORAM BAIXADOS:")
        print("=" * 80)
        print(f"Total: {len(baixados)}")

        if baixados:
            for c in baixados:
                # Formata a data
                data_str = c["data_baixa"]
                if len(data_str) == 8:  # YYYYMMDD
                    data_formatada = f"{data_str[6:8]}/{data_str[4:6]}/{data_str[:4]}"
                else:
                    data_formatada = data_str

                print(f"\n  Contrato: {c['contrato']}")
                print(f"  Data Baixa: {data_formatada} ({data_str})")
                print(f"  Mes Embarque: {c['mes_embarque']}")
        else:
            print("\n  [!] Nenhum contrato foi baixado")

        print("\n6. ANALISE DA RESPOSTA DA IA:")
        print("=" * 80)

        contratos_baixados_lista = sorted([c["contrato"] for c in baixados])
        ia_disse_contratos = sorted(['530/25', '531/25'])

        print(f"\nIA disse:")
        print(f"  - Quantidade: 2 contratos")
        print(f"  - Contratos: 530/25, 531/25")
        print(f"  - Afirmou: 'Em novembro e dezembro de 2025' foram baixados")

        print(f"\nBanco tem:")
        print(f"  - Quantidade: {len(baixados)} contratos")
        print(f"  - Contratos: {', '.join(contratos_baixados_lista) if contratos_baixados_lista else 'nenhum'}")

        if baixados:
            print(f"\n  Datas de baixa:")
            for c in baixados:
                data_str = c["data_baixa"]
                if len(data_str) == 8:
                    ano = data_str[:4]
                    mes = data_str[4:6]
                    dia = data_str[6:8]
                    print(f"    - {c['contrato']}: {dia}/{mes}/{ano}")

        print("\n7. VERIFICACAO:")
        print("=" * 80)

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
            print(f"[X] Contratos incorretos: IA disse {ia_disse_contratos}, banco tem {contratos_baixados_lista}")
            contratos_corretos = False

        # Verifica quando foram baixados
        print("\n[!] ANALISE CRITICA:")
        if baixados:
            todos_em_novdez = True
            for c in baixados:
                data_str = c["data_baixa"]
                if len(data_str) >= 6:
                    ano_mes = data_str[:6]  # YYYYMM
                    if ano_mes not in ["202511", "202512"]:
                        todos_em_novdez = False
                        mes_ano = f"{data_str[4:6]}/{data_str[:4]}"
                        print(f"  [!] Contrato {c['contrato']} foi baixado em {mes_ano}, NAO em nov/dez 2025")

            if not todos_em_novdez:
                print("\n  [X] A IA disse 'Em novembro e dezembro de 2025' mas os contratos")
                print("      foram baixados em outro periodo!")
                resposta_precisa = False
            else:
                print("\n  [OK] Contratos foram realmente baixados em nov/dez 2025")
                resposta_precisa = True
        else:
            resposta_precisa = False

        print("\n8. RESULTADO FINAL:")
        print("=" * 80)

        if qtd_correta and contratos_corretos:
            print("\n" + "=" * 80)
            if resposta_precisa:
                print("[OK][OK][OK] RESPOSTA DA IA ESTA 100% CORRETA! [OK][OK][OK]")
            else:
                print("[OK][OK][~] RESPOSTA DA IA ESTA PARCIALMENTE CORRETA [OK][OK][~]")
            print("=" * 80)
            print("\n[OK] Quantidade: 2 contratos")
            print("[OK] Contratos: 530/25 e 531/25")
            if not resposta_precisa:
                print("[~] MAS: Os contratos foram baixados FORA de nov/dez 2025")
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
    test_frey_completo()
