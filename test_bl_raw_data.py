"""
Investiga como o campo numeroBL está sendo retornado
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_bl_raw():
    """Mostra dados brutos do campo numeroBL"""
    print("=" * 80)
    print("INVESTIGACAO - CAMPO numeroBL")
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

        # Mostra alguns exemplos de cada tipo
        print("3. EXEMPLOS DE CONTRATOS:")
        print("-" * 80)

        # Com BL
        com_bl = [r for r in results if r.get("numeroBL") and str(r.get("numeroBL")).strip()]
        print(f"\nCOM BL ({len(com_bl)} contratos):")
        for i, row in enumerate(com_bl[:5], 1):
            print(f"\n  Exemplo {i}:")
            print(f"    Cliente: {row.get('cliente')}")
            print(f"    Contrato: {row.get('contrato')}")
            print(f"    numeroBL: '{row.get('numeroBL')}'")
            print(f"    saidaNavio: {row.get('saidaNavio')}")
            print(f"    mesEmbarque: {row.get('mesEmbarque')}")

        # Sem BL
        sem_bl = [r for r in results if not (r.get("numeroBL") and str(r.get("numeroBL")).strip())]
        print(f"\n\nSEM BL ({len(sem_bl)} contratos):")
        for i, row in enumerate(sem_bl[:5], 1):
            print(f"\n  Exemplo {i}:")
            print(f"    Cliente: {row.get('cliente')}")
            print(f"    Contrato: {row.get('contrato')}")
            print(f"    numeroBL: '{row.get('numeroBL')}'")
            print(f"    saidaNavio: {row.get('saidaNavio')}")
            print(f"    mesEmbarque: {row.get('mesEmbarque')}")

        # Testa contratos específicos que a IA mencionou incorretamente
        print("\n\n4. CONTRATOS QUE A IA MENCIONOU INCORRETAMENTE:")
        print("-" * 80)

        contratos_teste = ["400/25A", "400/25B", "256/25R", "256/25S", "544/25", "594/25"]

        for contrato_busca in contratos_teste:
            encontrado = False
            for row in results:
                contrato = str(row.get("contrato", "")).strip()
                if contrato == contrato_busca:
                    encontrado = True
                    tem_bl = row.get("numeroBL") and str(row.get("numeroBL")).strip()
                    print(f"\n  Contrato: {contrato}")
                    print(f"    Cliente: {row.get('cliente')}")
                    print(f"    numeroBL: '{row.get('numeroBL')}' -> {'TEM BL' if tem_bl else 'NAO TEM BL'}")
                    print(f"    saidaNavio: {row.get('saidaNavio')}")
                    print(f"    mesEmbarque: {row.get('mesEmbarque')}")
                    break

            if not encontrado:
                print(f"\n  Contrato {contrato_busca}: NAO ENCONTRADO em janeiro 2026")

        print("\n" + "=" * 80)
        print("[OK] INVESTIGACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_bl_raw()
