"""
Valida: Contratos do FREY A/S baixados em novembro e dezembro 2025
Pergunta: Quantos contratos do cliente FREY A/S em novembro e dezembro de 2025
          ja foram baixados financeiramente? Liste os numeros dos contratos.
Resposta IA:
  - 2 contratos foram baixados
  - Contratos: 530/25 e 531/25
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from decimal import Decimal

def test_frey_baixados():
    """Valida contratos FREY A/S baixados em nov/dez 2025"""
    print("=" * 80)
    print("VALIDACAO - FREY A/S: Contratos baixados em nov/dez 2025")
    print("=" * 80)

    try:
        print("\n1. RESPOSTA DA IA:")
        print("-" * 80)
        print("Pergunta: Quantos contratos do cliente FREY A/S em novembro e")
        print("          dezembro de 2025 ja foram baixados financeiramente?")
        print("          Liste os numeros dos contratos.")
        print("")
        print("Resposta IA:")
        print("  - Quantidade: 2 contratos")
        print("  - Contratos: 530/25 e 531/25")

        print("\n2. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n3. Buscando TODOS os contratos do cliente FREY A/S")
        print("-" * 80)

        # Busca todos os contratos do FREY
        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        print(f"Total de registros no banco: {len(result)}")

        # Filtra por cliente FREY
        frey_todos = []
        for r in result:
            cliente = r.get("cliente", "").strip().upper()
            if "FREY" in cliente:
                frey_todos.append(r)

        print(f"Total de registros do FREY: {len(frey_todos)}")

        print("\n4. Filtrando por mes de embarque: novembro e dezembro 2025")
        print("-" * 80)

        frey_nov_dez = []
        for r in frey_todos:
            mes_embarque = r.get("mesEmbarque", "").strip()
            # Aceita 2025/11 ou 2025/12
            if mes_embarque in ["2025/11", "2025/12"]:
                frey_nov_dez.append(r)

        print(f"Contratos FREY em nov/dez 2025: {len(frey_nov_dez)}")

        if frey_nov_dez:
            print("\nTodos os contratos FREY em nov/dez 2025:")
            for r in frey_nov_dez:
                contrato = r.get("contrato", "").strip()
                mes = r.get("mesEmbarque", "").strip()
                data_baixa = r.get("dataBaixa", "")
                tem_baixa = bool(data_baixa and str(data_baixa).strip())

                baixa_str = str(data_baixa).strip() if tem_baixa else "SEM BAIXA"
                print(f"  - Contrato: {contrato:10} | Mes: {mes} | Data Baixa: {baixa_str}")

        print("\n5. Filtrando: APENAS os que foram baixados financeiramente")
        print("-" * 80)

        frey_baixados = []
        for r in frey_nov_dez:
            data_baixa = r.get("dataBaixa", "")
            # Considera baixado se tem data de baixa
            tem_baixa = bool(data_baixa and str(data_baixa).strip() and str(data_baixa).strip() != "None")

            if tem_baixa:
                contrato = r.get("contrato", "").strip()
                frey_baixados.append({
                    "contrato": contrato,
                    "mes_embarque": r.get("mesEmbarque", "").strip(),
                    "data_baixa": str(data_baixa).strip(),
                    "cliente": r.get("cliente", "").strip()
                })

        print(f"Contratos FREY baixados em nov/dez 2025: {len(frey_baixados)}")

        if frey_baixados:
            print("\nDetalhes dos contratos baixados:")
            for c in frey_baixados:
                print(f"  - {c['contrato']:10} | Mes: {c['mes_embarque']} | Baixa: {c['data_baixa']} | Cliente: {c['cliente'][:30]}")

        print("\n6. COMPARACAO:")
        print("=" * 80)

        # Validacao 1: Quantidade de contratos
        print("\n6.1. QUANTIDADE DE CONTRATOS BAIXADOS:")
        print(f"  IA disse: 2 contratos")
        print(f"  Banco tem: {len(frey_baixados)} contratos")

        if len(frey_baixados) == 2:
            print("  [OK] CORRETO")
            quantidade_correta = True
        else:
            print("  [X] INCORRETO")
            quantidade_correta = False

        # Validacao 2: Numeros dos contratos
        print("\n6.2. NUMEROS DOS CONTRATOS:")
        print(f"  IA disse: 530/25 e 531/25")

        contratos_banco = sorted([c['contrato'] for c in frey_baixados])
        print(f"  Banco tem: {', '.join(contratos_banco)}")

        contratos_ia = sorted(['530/25', '531/25'])
        if contratos_banco == contratos_ia:
            print("  [OK] CORRETO")
            contratos_corretos = True
        else:
            print("  [X] INCORRETO")
            contratos_corretos = False

        print("\n7. INFORMACOES ADICIONAIS:")
        print("-" * 80)

        if frey_baixados:
            for c in frey_baixados:
                print(f"\nContrato: {c['contrato']}")
                print(f"  Cliente: {c['cliente']}")
                print(f"  Mes Embarque: {c['mes_embarque']}")
                print(f"  Data Baixa: {c['data_baixa']}")

        print("\n8. RESULTADO FINAL:")
        print("=" * 80)

        if quantidade_correta and contratos_corretos:
            print("\n" + "=" * 80)
            print("[OK][OK][OK] RESPOSTA DA IA ESTA 100% CORRETA! [OK][OK][OK]")
            print("=" * 80)
            print("\nTodos os campos conferem:")
            print(f"  [OK] Quantidade: {len(frey_baixados)} contratos")
            print(f"  [OK] Contratos: {', '.join(contratos_banco)}")
        else:
            print("\n" + "=" * 80)
            print("[X][X][X] RESPOSTA DA IA ESTA INCORRETA! [X][X][X]")
            print("=" * 80)
            print("\nErros encontrados:")
            if not quantidade_correta:
                print(f"  [X] Quantidade: IA disse 2, banco tem {len(frey_baixados)}")
            if not contratos_corretos:
                print(f"  [X] Contratos: IA disse 530/25, 531/25, banco tem {', '.join(contratos_banco)}")

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
    test_frey_baixados()
