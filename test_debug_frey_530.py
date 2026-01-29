"""
Debug: Verifica TODOS os campos do contrato 530/25 do FREY
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
import json

def test_debug_530():
    """Debug contrato 530/25"""
    print("=" * 80)
    print("DEBUG - Contrato 530/25 do FREY A/S")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado")

        print("\n2. Buscando contrato 530/25")
        print("-" * 80)

        result = sql_client.execute_function("dbo.IA_Vendas")

        if not result:
            print("[ERRO] Nenhum resultado retornado")
            return

        # Procura 530/25
        contrato_530 = None
        for r in result:
            if r.get("contrato", "").strip() == "530/25":
                contrato_530 = r
                break

        if not contrato_530:
            print("[X] Contrato 530/25 NAO encontrado!")
            return

        print("[OK] Contrato 530/25 encontrado")

        print("\n3. TODOS OS CAMPOS DO CONTRATO 530/25:")
        print("=" * 80)

        # Mostra todos os campos
        for key, value in sorted(contrato_530.items()):
            # Formata o valor
            if value is None:
                valor_str = "NULL"
            elif isinstance(value, str):
                valor_str = f'"{value.strip()}"' if value.strip() else '""'
            else:
                valor_str = str(value)

            print(f"{key:30} = {valor_str}")

        print("\n4. CAMPOS IMPORTANTES:")
        print("-" * 80)
        print(f"contrato        = {contrato_530.get('contrato', 'N/A')}")
        print(f"cliente         = {contrato_530.get('cliente', 'N/A')}")
        print(f"mesEmbarque     = {contrato_530.get('mesEmbarque', 'N/A')}")
        print(f"dataBaixa       = {contrato_530.get('dataBaixa', 'N/A')}")
        print(f"dataEmissao     = {contrato_530.get('dataEmissao', 'N/A')}")
        print(f"saidaNavio      = {contrato_530.get('saidaNavio', 'N/A')}")
        print(f"numeroBL        = {contrato_530.get('numeroBL', 'N/A')}")

        print("\n5. VERIFICACAO dataBaixa:")
        print("-" * 80)
        data_baixa = contrato_530.get('dataBaixa')
        print(f"Valor: {data_baixa}")
        print(f"Tipo: {type(data_baixa)}")
        print(f"Bool: {bool(data_baixa)}")
        if data_baixa:
            print(f"String: '{str(data_baixa).strip()}'")
            print(f"Diferente de 'None': {str(data_baixa).strip() != 'None'}")

        print("\n" + "=" * 80)
        print("[OK] DEBUG CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_debug_530()
