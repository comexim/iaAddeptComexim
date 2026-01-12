"""
Script de teste de conexao com SQL Server
"""
import sys
import os

# Adiciona o diretorio raiz ao path
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.core.database import sql_client


def test_basic_connection():
    """Testa conexao basica"""
    print("=" * 60)
    print("TESTE DE CONEXAO SQL SERVER - AGENTE COMEXIM")
    print("=" * 60)
    print()

    print("[INFO] Configuracoes:")
    print(f"   Host: {settings.sql_server_host}")
    print(f"   Port: {settings.sql_server_port}")
    print(f"   Database: {settings.sql_server_database}")
    print(f"   User: {settings.sql_server_user}")
    print(f"   Driver: {settings.sql_server_driver}")
    print()

    print("[TEST] Testando conexao basica...")
    try:
        if sql_client.test_connection():
            print("[OK] Conexao estabelecida com sucesso!\n")
            return True
        else:
            print("[ERRO] Falha ao conectar\n")
            return False
    except Exception as e:
        print(f"[ERRO] {e}\n")
        return False


def test_query_vendas():
    """Testa query na funcao IA_Vendas"""
    print("=" * 60)
    print("TESTE: IA_Vendas() - Ultimas vendas")
    print("=" * 60)
    print()

    try:
        # Tenta buscar vendas de dezembro/2024 (se houver)
        filters = {"mesEmbarque": "2024/12"}
        print(f"[QUERY] SELECT * FROM IA_Vendas() WHERE mesEmbarque = '2024/12'")
        print()

        results = sql_client.execute_function("IA_Vendas", filters)

        if results:
            print(f"[OK] Retornou {len(results)} registro(s)\n")
            print("[DATA] Primeiros 3 registros (se houver):")
            print("-" * 60)
            for i, row in enumerate(results[:3], 1):
                print(f"\nRegistro {i}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
            print()
            return True
        else:
            print("[AVISO] Nenhum registro encontrado para mesEmbarque = '2024/12'")
            print("        Isso e normal se nao houver dados desse periodo.\n")
            return True

    except Exception as e:
        print(f"[ERRO] Erro ao executar query: {e}\n")
        return False


def test_query_saldo_bancario():
    """Testa query na funcao IA_SaldoBancario (sem filtros)"""
    print("=" * 60)
    print("TESTE: IA_SaldoBancario() - Saldo atual")
    print("=" * 60)
    print()

    try:
        print("[QUERY] SELECT * FROM IA_SaldoBancario()")
        print()

        results = sql_client.execute_function("IA_SaldoBancario")

        if results:
            print(f"[OK] Retornou {len(results)} registro(s)\n")
            print("[DATA] Dados retornados:")
            print("-" * 60)
            for i, row in enumerate(results, 1):
                print(f"\nConta {i}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
            print()
            return True
        else:
            print("[AVISO] Nenhum registro encontrado")
            print("        Verifique se a funcao IA_SaldoBancario() existe no banco.\n")
            return False

    except Exception as e:
        print(f"[ERRO] Erro ao executar query: {e}\n")
        return False


def test_query_estoque():
    """Testa query na funcao IA_Estoque (sem filtros)"""
    print("=" * 60)
    print("TESTE: IA_Estoque() - Estoque atual")
    print("=" * 60)
    print()

    try:
        print("[QUERY] SELECT * FROM IA_Estoque()")
        print()

        results = sql_client.execute_function("IA_Estoque")

        if results:
            print(f"[OK] Retornou {len(results)} registro(s)\n")
            print("[DATA] Primeiros 5 produtos:")
            print("-" * 60)
            for i, row in enumerate(results[:5], 1):
                print(f"\nProduto {i}:")
                for key, value in row.items():
                    print(f"  {key}: {value}")
            print()
            return True
        else:
            print("[AVISO] Nenhum registro encontrado\n")
            return False

    except Exception as e:
        print(f"[ERRO] Erro ao executar query: {e}\n")
        return False


def main():
    """Executa todos os testes"""
    print("\n")
    print("[START] INICIANDO TESTES DE CONEXAO E QUERIES")
    print("\n")

    # Teste 1: Conexao basica
    if not test_basic_connection():
        print("[FAIL] Teste de conexao falhou. Verifique as configuracoes no .env")
        print("\nDicas:")
        print("  1. Verifique se SQL_SERVER_DATABASE esta configurado")
        print("  2. Verifique credenciais (user/password)")
        print("  3. Verifique se o servidor esta acessivel")
        print("  4. Verifique se ODBC Driver 17 esta instalado")
        return

    print("\n")

    # Teste 2: Query IA_SaldoBancario (mais simples, sem filtros)
    test_query_saldo_bancario()

    print("\n")

    # Teste 3: Query IA_Estoque
    test_query_estoque()

    print("\n")

    # Teste 4: Query IA_Vendas (com filtros)
    test_query_vendas()

    print("\n")
    print("=" * 60)
    print("TESTES CONCLUIDOS")
    print("=" * 60)
    print()

    # Fecha conexao
    sql_client.close()
    print("[DONE] Conexao fechada")
    print()


if __name__ == "__main__":
    main()
