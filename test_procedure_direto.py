"""
Testa a procedure usp_LS_FILIAIS direto no banco de dados
"""
import sys
sys.path.insert(0, 'c:\\Users\\pedro\\Desktop\\agente-comexim')

from app.core.database import SQLServerClient

def test_procedure_direto():
    """Executa a procedure direto no banco para verificar o que retorna"""

    client = SQLServerClient()

    print("=" * 80)
    print("TESTE: usp_LS_FILIAIS direto no banco")
    print("=" * 80)

    # Teste 1: Com parâmetro FILIAIS
    print("\n[TESTE 1] EXEC usp_LS_FILIAIS @FILIAL='FILIAIS'")
    print("-" * 80)
    try:
        results = client.execute_procedure("usp_LS_FILIAIS", {"FILIAL": "FILIAIS"})
        print(f"[OK] Sucesso! Retornou {len(results)} registros")
        if results:
            print(f"\nPrimeiro registro:")
            for key, value in results[0].items():
                print(f"  {key}: {value}")
        else:
            print("[AVISO] Procedure executou mas retornou 0 registros (lista vazia)")
            print("Isso significa que a procedure NAO tem SELECT ou nao ha dados")
    except Exception as e:
        print(f"[ERRO] {e}")
        import traceback
        traceback.print_exc()

    # Teste 2: Com parâmetro COBRA
    print("\n\n[TESTE 2] EXEC usp_LS_FILIAIS @FILIAL='COBRA'")
    print("-" * 80)
    try:
        results = client.execute_procedure("usp_LS_FILIAIS", {"FILIAL": "COBRA"})
        print(f"[OK] Sucesso! Retornou {len(results)} registros")
        if results:
            print(f"\nPrimeiro registro:")
            for key, value in results[0].items():
                print(f"  {key}: {value}")
        else:
            print("[AVISO] Procedure executou mas retornou 0 registros")
    except Exception as e:
        print(f"[ERRO] {e}")

    # Teste 3: Com parâmetro CUSA
    print("\n\n[TESTE 3] EXEC usp_LS_FILIAIS @FILIAL='CUSA'")
    print("-" * 80)
    try:
        results = client.execute_procedure("usp_LS_FILIAIS", {"FILIAL": "CUSA"})
        print(f"[OK] Sucesso! Retornou {len(results)} registros")
        if results:
            print(f"\nPrimeiro registro:")
            for key, value in results[0].items():
                print(f"  {key}: {value}")
        else:
            print("[AVISO] Procedure executou mas retornou 0 registros")
    except Exception as e:
        print(f"[ERRO] {e}")

    # Teste 4: Sem parâmetro
    print("\n\n[TESTE 4] EXEC usp_LS_FILIAIS (sem parâmetro)")
    print("-" * 80)
    try:
        results = client.execute_procedure("usp_LS_FILIAIS", None)
        print(f"[OK] Sucesso! Retornou {len(results)} registros")
        if results:
            print(f"\nPrimeiro registro:")
            for key, value in results[0].items():
                print(f"  {key}: {value}")
        else:
            print("[AVISO] Procedure executou mas retornou 0 registros")
    except Exception as e:
        print(f"[ERRO] {e}")

    print("\n" + "=" * 80)
    print("Testes finalizados")
    print("=" * 80)

if __name__ == "__main__":
    test_procedure_direto()
