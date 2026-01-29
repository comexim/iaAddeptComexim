"""
Testa query sobre ID Protheus de contrato
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

def test_id_protheus():
    """Testa query sobre ID Protheus"""
    print("=" * 80)
    print("TESTE - ID PROTHEUS DO CONTRATO 021/25")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        print("2. Buscando contrato 021/25 diretamente no SQL...")

        # Usa o método execute_query do sql_client
        query = """
            SELECT TOP 5 *
            FROM dbo.IA_Vendas(NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            WHERE numeroContrato LIKE '%021/25%'
        """

        result = sql_client.execute_query(query)

        if result and len(result) > 0:
            print(f"\nResultados encontrados: {len(result)}")

            # Pega as colunas do primeiro resultado
            colunas = list(result[0].keys())
            print(f"\nTotal de colunas: {len(colunas)}")

            # Procura colunas relacionadas a ID ou Protheus
            id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]
            print(f"\nColunas com ID/Protheus/RecNo: {id_cols}")

            print("\n\nDados do contrato 021/25:")
            for i, row in enumerate(result, 1):
                print(f"\n--- Registro {i} ---")
                print(f"Contrato: {row.get('numeroContrato')}")
                print(f"Cliente: {row.get('cliente')}")

                # Mostra campos relacionados a ID
                if id_cols:
                    print("\nCampos de ID/Protheus:")
                    for col in id_cols:
                        print(f"  {col}: {row.get(col)}")
                else:
                    print("\nNenhum campo de ID/Protheus encontrado!")
                    print("\nPrimeiros 20 campos disponíveis:")
                    for col in list(colunas)[:20]:
                        print(f"  {col}: {row.get(col)}")
        else:
            print("\n[AVISO] Contrato 021/25 não encontrado!")

            # Tenta buscar contratos que começam com 021
            query2 = """
                SELECT numeroContrato, cliente
                FROM dbo.IA_Vendas(NULL, NULL, NULL, NULL, NULL, NULL, NULL)
                WHERE numeroContrato LIKE '021%'
            """

            result2 = sql_client.execute_query(query2)
            if result2:
                print(f"\nContratos que começam com 021: {len(result2)}")
                for c in result2[:5]:
                    print(f"  - {c.get('numeroContrato')} ({c.get('cliente')})")
            else:
                print("\nNenhum contrato encontrado que comece com 021")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
