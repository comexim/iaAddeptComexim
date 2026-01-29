"""
Tenta buscar dados de cotação com diferentes filtros
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from datetime import datetime, timedelta

def testar_cotacao():
    """Testa IA_Cotacao com diferentes filtros"""
    print("=" * 80)
    print("TESTE - IA_Cotacao() com filtros")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        # Teste 1: Sem filtros
        print("2. Teste 1: SELECT * FROM IA_Cotacao() (sem filtros)")
        result = sql_client.execute_function("dbo.IA_Cotacao", filters=None)
        print(f"   Resultado: {len(result)} registros\n")

        if len(result) == 0:
            print("3. Tentando com filtros de data...")
            
            # Teste 2: Com data
            filtros_teste = [
                {"data": "2026-01-01"},
                {"data": "2025-12-01"},
                {"data": "2025-01-01"},
                {"emissao": "2026-01-01"},
                {"emissao": "2025-12-01"},
            ]
            
            for i, filtro in enumerate(filtros_teste, 1):
                print(f"\n   Teste {i+1}: Filtro {filtro}")
                try:
                    result = sql_client.execute_function("dbo.IA_Cotacao", filters=filtro)
                    print(f"   Resultado: {len(result)} registros")
                    if len(result) > 0:
                        print("   [OK] Encontrou dados!")
                        colunas = list(result[0].keys())
                        print(f"   Colunas: {len(colunas)}")
                        print(f"   Primeiro registro: {result[0]}")
                        break
                except Exception as e:
                    print(f"   Erro: {e}")
        else:
            print(f"\n[OK] Função retornou {len(result)} registros sem filtros")
            colunas = list(result[0].keys())
            print(f"Total de colunas: {len(colunas)}\n")
            
            print("COLUNAS:")
            for i, col in enumerate(colunas, 1):
                print(f"{i:3d}. {col}")
            
            print(f"\n\nPRIMEIRO REGISTRO:")
            for col in colunas:
                print(f"{col}: {result[0].get(col)}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    testar_cotacao()
