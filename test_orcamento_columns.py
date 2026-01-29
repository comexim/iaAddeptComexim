"""
Script de teste para verificar colunas retornadas por IA_Orcamento()
"""
import asyncio
import sys
import os

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client


def test_orcamento_columns():
    """Testa e exibe colunas da função IA_Orcamento()"""
    print("=" * 80)
    print("TESTE DE COLUNAS - IA_Orcamento()")
    print("=" * 80)

    try:
        print("\n1. Testando conexao com SQL Server...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar no SQL Server")
            return

        print("[OK] Conexao estabelecida com sucesso\n")

        # Executa função
        print("2. Executando SELECT * FROM IA_Orcamento()...")
        results = sql_client.execute_function("IA_Orcamento")

        if not results:
            print("[AVISO] Nenhum registro retornado")
            return

        print(f"[OK] {len(results)} registros retornados\n")

        # Exibe colunas
        print("3. COLUNAS DISPONIVEIS NA FUNCAO IA_Orcamento():")
        print("-" * 80)

        columns = list(results[0].keys())
        for i, col in enumerate(columns, 1):
            print(f"  {i:2d}. {col}")

        print("-" * 80)
        print(f"\nTotal de colunas: {len(columns)}")

        # Exibe primeiros 3 registros como exemplo
        print("\n4. EXEMPLO DE DADOS (primeiros 3 registros):")
        print("-" * 80)
        for i, row in enumerate(results[:3], 1):
            print(f"\nRegistro {i}:")
            for key, value in row.items():
                print(f"  {key}: {value}")

        print("\n" + "=" * 80)
        print("[OK] TESTE CONCLUIDO COM SUCESSO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()


if __name__ == "__main__":
    test_orcamento_columns()
