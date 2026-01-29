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
        cursor = sql_client.connection.cursor()
        
        # Busca o contrato
        cursor.execute("""
            SELECT TOP 5 * 
            FROM dbo.IA_Vendas(NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            WHERE numeroContrato LIKE '%021/25%'
        """)
        
        colunas = [col[0] for col in cursor.description]
        resultados = cursor.fetchall()
        
        print(f"Colunas disponíveis ({len(colunas)}):")
        # Procura colunas relacionadas a ID ou Protheus
        id_cols = [c for c in colunas if 'id' in c.lower() or 'protheus' in c.lower() or 'recno' in c.lower() or 'r_e_c' in c.lower()]
        print(f"Colunas com ID/Protheus: {id_cols}")
        
        print(f"\nResultados encontrados: {len(resultados)}")
        
        if resultados:
            print("\nDados do contrato 021/25:")
            for row in resultados:
                row_dict = dict(zip(colunas, row))
                print(f"\nContrato: {row_dict.get('numeroContrato')}")
                print(f"Cliente: {row_dict.get('cliente')}")
                
                # Mostra campos relacionados a ID
                for col in id_cols:
                    print(f"{col}: {row_dict.get(col)}")
        else:
            print("\n[AVISO] Contrato 021/25 não encontrado!")
            
            # Tenta buscar contratos que começam com 021
            cursor.execute("""
                SELECT numeroContrato, cliente
                FROM dbo.IA_Vendas(NULL, NULL, NULL, NULL, NULL, NULL, NULL)
                WHERE numeroContrato LIKE '021%'
            """)
            contratos_021 = cursor.fetchall()
            print(f"\nContratos que começam com 021: {len(contratos_021)}")
            for c in contratos_021[:5]:
                print(f"  - {c[0]} ({c[1]})")

        cursor.close()

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_id_protheus()
