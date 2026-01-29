"""
Mapeia todos os campos da função IA_Compras()
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_campos_compras():
    """Mapeia campos de IA_Compras()"""
    print("=" * 80)
    print("MAPEAMENTO - IA_Compras()")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Executando: SELECT * FROM IA_Compras() WHERE emissao >= '20251205'")
        result = sql_client.execute_function("dbo.IA_Compras", filters={"emissao": "20251205"})

        if not result:
            print("[AVISO] Nenhum resultado retornado")
            return

        print(f"[OK] {len(result)} registros retornados\n")

        # Pega o primeiro registro para mapear colunas
        primeiro = result[0]
        colunas = list(primeiro.keys())

        print("=" * 80)
        print(f"TOTAL DE COLUNAS: {len(colunas)}")
        print("=" * 80)

        print("\nLISTA DE COLUNAS:")
        print("-" * 80)
        for i, col in enumerate(colunas, 1):
            valor = primeiro[col]
            tipo = type(valor).__name__

            # Mostra valor de exemplo (limitado)
            if isinstance(valor, str):
                valor_exemplo = valor[:50] if len(str(valor)) > 50 else valor
            else:
                valor_exemplo = valor

            print(f"{i:2}. {col:30} ({tipo:10}) = {valor_exemplo}")

        print("\n" + "=" * 80)
        print("EXEMPLOS DE REGISTROS:")
        print("=" * 80)
        for i, reg in enumerate(result[:3], 1):
            print(f"\nRegistro {i}:")
            print(f"  Emissão: {reg.get('emissao')}")
            print(f"  Fornecedor: {reg.get('fornecedor', 'N/A')}")
            print(f"  Produto: {reg.get('produto', 'N/A')}")
            print(f"  Quantidade: {reg.get('quantidade', 'N/A')}")
            print(f"  Valor: {reg.get('valor', 'N/A')}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_campos_compras()
