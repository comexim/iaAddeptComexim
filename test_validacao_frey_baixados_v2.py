"""
Valida: Contratos do FREY A/S baixados em novembro e dezembro 2025
DUAS INTERPRETACOES:
1. Contratos com mes de embarque nov/dez que foram baixados
2. Contratos que foram baixados DURANTE nov/dez (data de baixa em nov/dez)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_frey_baixados_ambas_interpretacoes():
    """Valida contratos FREY A/S - ambas interpretacoes"""
    print("=" * 80)
    print("VALIDACAO - FREY A/S: Contratos baixados - Ambas interpretacoes")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Quantos contratos do cliente FREY A/S em novembro e")
        print("          dezembro de 2025 ja foram baixados financeiramente?")
        print("")
        print("Resposta IA: 2 contratos (530/25 e 531/25)")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando TODOS os contratos do cliente FREY A/S")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        # Filtra por cliente FREY
        frey_todos = []
        for r in result:
            cliente = r.get("cliente", "").strip().upper()
            if "FREY" in cliente:
                frey_todos.append(r)

        print(f"Total de contratos FREY (todos os periodos): {len(frey_todos)}")

        print("\n4. INTERPRETACAO 1: Contratos com MES DE EMBARQUE nov/dez 2025 que foram baixados")
        print("=" * 80)

        frey_embarque_novdez = []
        for r in frey_todos:
            mes_embarque = r.get("mesEmbarque", "").strip()
            if mes_embarque in ["2025/11", "2025/12"]:
                frey_embarque_novdez.append(r)

        print(f"\nTotal contratos FREY com embarque nov/dez 2025: {len(frey_embarque_novdez)}")

        if frey_embarque_novdez:
            print("\nTodos os contratos:")
            for r in frey_embarque_novdez:
                contrato = r.get("contrato", "").strip()
                mes = r.get("mesEmbarque", "").strip()
                data_baixa = r.get("dataBaixa", "")
                tem_baixa = bool(data_baixa and str(data_baixa).strip() and str(data_baixa).strip() != "None")
                baixa_str = str(data_baixa).strip() if tem_baixa else "SEM BAIXA"
                print(f"  {contrato:10} | Embarque: {mes} | Baixa: {baixa_str}")

        baixados_interp1 = [r for r in frey_embarque_novdez
                           if r.get("dataBaixa") and str(r.get("dataBaixa")).strip() and str(r.get("dataBaixa")).strip() != "None"]

        print(f"\nContratos BAIXADOS (interpretacao 1): {len(baixados_interp1)}")
        if baixados_interp1:
            for r in baixados_interp1:
                print(f"  - {r.get('contrato', '').strip()}")

        print("\n5. INTERPRETACAO 2: Contratos que foram BAIXADOS DURANTE nov/dez 2025")
        print("=" * 80)

        # Para cada contrato FREY, verifica se a data de baixa esta em nov/dez 2025
        frey_baixados_em_novdez = []
        for r in frey_todos:
            data_baixa = r.get("dataBaixa", "")
            if data_baixa and str(data_baixa).strip() and str(data_baixa).strip() != "None":
                data_str = str(data_baixa).strip()
                # Formato: YYYYMMDD
                # Nov 2025: 20251101 a 20251130
                # Dez 2025: 20251201 a 20251231
                if len(data_str) >= 6:
                    ano_mes = data_str[:6]  # YYYYMM
                    if ano_mes in ["202511", "202512"]:
                        frey_baixados_em_novdez.append(r)

        print(f"\nContratos FREY baixados DURANTE nov/dez 2025: {len(frey_baixados_em_novdez)}")

        if frey_baixados_em_novdez:
            print("\nDetalhes:")
            for r in frey_baixados_em_novdez:
                contrato = r.get("contrato", "").strip()
                mes_embarque = r.get("mesEmbarque", "").strip()
                data_baixa = r.get("dataBaixa", "")
                print(f"  Contrato: {contrato:10} | Embarque: {mes_embarque} | Data Baixa: {data_baixa}")

        contratos_baixados_interp2 = sorted([r.get("contrato", "").strip() for r in frey_baixados_em_novdez])

        print("\n6. COMPARACAO COM RESPOSTA DA IA:")
        print("=" * 80)

        ia_disse_quantidade = 2
        ia_disse_contratos = sorted(['530/25', '531/25'])

        print(f"\nIA disse: {ia_disse_quantidade} contratos ({', '.join(ia_disse_contratos)})")

        print("\n6.1. Interpretacao 1 (mes embarque nov/dez):")
        print(f"  Banco tem: {len(baixados_interp1)} contratos")
        if len(baixados_interp1) == ia_disse_quantidade:
            print("  [OK] Quantidade correta para interpretacao 1")
            interp1_correta = True
        else:
            print("  [X] Quantidade incorreta para interpretacao 1")
            interp1_correta = False

        print("\n6.2. Interpretacao 2 (baixados DURANTE nov/dez):")
        print(f"  Banco tem: {len(frey_baixados_em_novdez)} contratos")
        print(f"  Contratos: {', '.join(contratos_baixados_interp2) if contratos_baixados_interp2 else 'nenhum'}")

        if len(frey_baixados_em_novdez) == ia_disse_quantidade and contratos_baixados_interp2 == ia_disse_contratos:
            print("  [OK] Interpretacao 2 CORRETA!")
            interp2_correta = True
        else:
            print("  [X] Interpretacao 2 incorreta")
            interp2_correta = False

        print("\n7. RESULTADO FINAL:")
        print("=" * 80)

        if interp2_correta:
            print("\n" + "=" * 80)
            print("[OK][OK][OK] RESPOSTA DA IA ESTA CORRETA! [OK][OK][OK]")
            print("=" * 80)
            print("\nA IA interpretou corretamente como:")
            print("'Contratos que foram BAIXADOS DURANTE novembro/dezembro 2025'")
            print(f"\nContratos: {', '.join(contratos_baixados_interp2)}")
            print(f"Quantidade: {len(frey_baixados_em_novdez)}")
        elif interp1_correta:
            print("\n[?] Interpretacao 1 esta correta, mas vazia")
        else:
            print("\n" + "=" * 80)
            print("[X][X][X] RESPOSTA DA IA ESTA INCORRETA! [X][X][X]")
            print("=" * 80)
            print("\nNenhuma das interpretacoes confere:")
            print(f"  Interp. 1 (embarque nov/dez): {len(baixados_interp1)} contratos")
            print(f"  Interp. 2 (baixados em nov/dez): {len(frey_baixados_em_novdez)} contratos")
            print(f"  IA disse: {ia_disse_quantidade} contratos")

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
    test_frey_baixados_ambas_interpretacoes()
