"""
Testa a tool pesquisa_despesa_venda
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools

def test_despesa_venda_tool():
    """Testa tool despesa_venda"""
    print("=" * 80)
    print("TESTE - Tool pesquisa_despesa_venda()")
    print("=" * 80)

    try:
        print("\n1. Conectando ao banco...")
        if not sql_client.test_connection():
            print("[ERRO] Falha ao conectar")
            return
        print("[OK] Conectado\n")

        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        print("2. Criando SQLTools...")
        sql_tools = SQLTools(user=FakeUser())
        print("[OK] SQLTools criado\n")

        print("3. Testando tool pesquisa_despesa_venda(contrato='235/25')...")
        result = sql_tools._pesquisa_despesa_venda(contrato="235/25")
        
        print(f"[OK] Retornou resultado\n")
        print("=" * 80)
        print("RESULTADO:")
        print("=" * 80)
        print(result[:1000])  # Primeiros 1000 chars
        if len(result) > 1000:
            print("\n...")
            print(result[-500:])  # Ultimos 500 chars
        print("=" * 80)
        
        print(f"\nTamanho total: {len(result)} caracteres")
        
        # Verifica se tem os campos principais
        campos_esperados = ["despesa", "fornecedor", "despesaRea", "despesaDolar"]
        tem_campos = all(campo in result for campo in campos_esperados)
        
        if tem_campos:
            print("[OK] Resultado contem todos os campos esperados")
        else:
            print("[AVISO] Alguns campos esperados nao foram encontrados")
            
        # Conta quantas despesas
        if "despesa" in result:
            num_despesas = result.count('"despesa"')
            print(f"[OK] Encontradas aproximadamente {num_despesas} despesas")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()
    finally:
        sql_client.close()

if __name__ == "__main__":
    test_despesa_venda_tool()
