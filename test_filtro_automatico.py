"""
Valida: Filtro automático para "sem valor fixado"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_filtro():
    """Valida filtro automático"""
    print("=" * 80)
    print("VALIDACAO - Filtro automático 'sem valor fixado'")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        # Primeira pergunta
        print("\n1. Pergunta: quantos contratos sem valor fixado em 12/2025?")
        print("-" * 80)
        sql_tools.user_query = "quantos contratos de exportação em 12/2025 não tem valor fixado?"
        result1 = sql_tools._pesquisa_vendas(periodo="12/2025")

        # Verifica se aplicou filtro
        if "FILTRO" in result1 or "sem valor fixado" in result1.lower():
            print("[OK] Filtro foi mencionado na resposta")

        # Conta quantos registros
        if "Total de registros SQL:" in result1:
            for linha in result1.split('\n'):
                if "Total de registros SQL:" in linha:
                    print(linha)
                    break

        # Procura o contrato 488/25
        if "488/25" in result1:
            print("\n[OK] Contrato 488/25 encontrado na resposta!")

            # Procura o diferencial
            linhas = result1.split('\n')
            for i, linha in enumerate(linhas):
                if "488/25" in linha or "COMEXIM EUROPE" in linha:
                    print(f"\nContexto do 488/25 (linhas {i-2} a {i+10}):")
                    for j in range(max(0, i-2), min(len(linhas), i+10)):
                        print(f"  {j}: {linhas[j][:120]}")
                    break

            # Procura campo "diferencial"
            print("\n\nLinhas que mencionam 'diferencial':")
            for i, linha in enumerate(linhas):
                if "diferencial" in linha.lower() and i < 100:
                    print(f"  {i}: {linha[:120]}")

        else:
            print("\n[X] Contrato 488/25 NÃO encontrado")
            print("\nPrimeiras 30 linhas:")
            for i, linha in enumerate(result1.split('\n')[:30]):
                print(f"  {i}: {linha}")

        # Segunda pergunta (simula contexto)
        print("\n\n2. Pergunta: qual o diferencial desse contrato?")
        print("-" * 80)
        sql_tools.user_query = "e qual é o diferencial desse contrato?"
        result2 = sql_tools._pesquisa_vendas(periodo="12/2025")

        # Verifica se tem dados desagregados
        print("\nVerificando se retornou dados desagregados...")
        if "488/25" in result2:
            print("[OK] 488/25 ainda aparece")

            # Procura diferencial
            linhas2 = result2.split('\n')
            for i, linha in enumerate(linhas2):
                if "diferencial" in linha.lower() and "488" in result2[max(0, i-20):i+20]:
                    print(f"\nLinha {i} (próxima ao 488/25): {linha[:120]}")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_filtro()
