"""
Mostra a resposta COMPLETA da tool para análise
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_response():
    """Mostra resposta completa da tool"""
    print("=" * 80)
    print("RESPOSTA COMPLETA DA TOOL")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        print("\nPergunta: Dos contratos exportados para Alemanha em dezembro de 2025,")
        print("          quantos já foram embarcados mas ainda não têm BL?")

        sql_tools.user_query = "Dos contratos exportados para Alemanha em dezembro de 2025, quantos já foram embarcados mas ainda não têm BL?"

        result = sql_tools._pesquisa_vendas(periodo="dezembro 2025")

        print("\n" + "=" * 80)
        print("SALVANDO RESPOSTA EM ARQUIVO...")
        print("=" * 80)

        # Salva em arquivo
        output_file = "alemanha_tool_response.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)

        linhas = result.split('\n')
        print(f"\n[OK] Resposta salva em: {output_file}")
        print(f"Total de linhas: {len(linhas)}")

        # Mostra informações relevantes
        print("\nProcurando 'ALEMANHA' na resposta:")
        for i, linha in enumerate(linhas):
            if "ALEMAN" in linha.upper():
                print(f"  Linha {i}: {linha[:100].encode('ascii', 'ignore').decode()}")

        print("\nProcurando 'sem BL' na resposta:")
        for i, linha in enumerate(linhas):
            if "SEM BL" in linha.upper():
                print(f"  Linha {i}: {linha[:100].encode('ascii', 'ignore').decode()}")

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_response()
