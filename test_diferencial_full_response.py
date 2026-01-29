"""
Valida: Resposta completa da tool para ver como diferencial é apresentado
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_full_response():
    """Valida resposta completa da tool"""
    print("=" * 80)
    print("VALIDACAO - Resposta completa da tool")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "contratos sem valor fixado em 12/2025"

        print("\n1. Chamando _pesquisa_vendas(periodo='12/2025')")
        print("-" * 80)

        result = sql_tools._pesquisa_vendas(periodo="12/2025")

        print("\n2. Procurando informações sobre ALEMANHA (país do 488/25):")
        print("=" * 80)

        linhas = result.split('\n')

        # Procura por ALEMANHA na seção CONTRATOS POR PAÍS
        print("\nNa seção CONTRATOS POR PAÍS:")
        in_contratos_pais = False
        for i, linha in enumerate(linhas):
            if "CONTRATOS POR PA" in linha.upper():
                in_contratos_pais = True
                continue
            if in_contratos_pais and "Dados agregados:" in linha:
                in_contratos_pais = False
                break
            if in_contratos_pais and "ALEMANHA" in linha.upper():
                # Imprime a linha da Alemanha e a próxima (com os contratos)
                print(linha)
                if i + 1 < len(linhas):
                    print(linhas[i + 1])
                break

        # Procura COMEXIM EUROPE na agregação por cliente
        print("\n\nNa agregação por cliente (COMEXIM EUROPE GMBH.):")
        print("-" * 80)

        # Encontra a seção de dados agregados (JSON)
        in_json = False
        json_lines = []
        brace_count = 0

        for linha in linhas:
            if "Dados agregados:" in linha:
                in_json = True
                continue

            if in_json:
                # Conta chaves para saber quando termina o JSON
                brace_count += linha.count('{') - linha.count('}')
                json_lines.append(linha)

                # Se voltou a 0, terminou o JSON
                if brace_count <= 0 and len(json_lines) > 10:
                    break

        # Procura COMEXIM EUROPE no JSON
        import json
        json_text = '\n'.join(json_lines)

        try:
            dados = json.loads(json_text)

            # Procura o cliente COMEXIM EUROPE
            for cliente_data in dados:
                cliente = cliente_data.get("cliente", "")
                if "COMEXIM EUROPE" in cliente.upper():
                    print(f"\nCliente: {cliente}")
                    print(f"Total de contratos: {cliente_data.get('total_contratos')}")
                    print(f"Contratos: {cliente_data.get('contratos', [])[:10]}")
                    print(f"Diferencial médio: {cliente_data.get('diferencial_medio')}")
                    print(f"Valor unitário médio: {cliente_data.get('valor_unitario_medio')}")
                    print(f"Valor fixado médio: {cliente_data.get('valor_fixado_medio')}")
                    print(f"Países: {list(cliente_data.get('paises', []))}")

                    # Se tem 3 contratos, mostra cada um
                    contratos = cliente_data.get('contratos', [])
                    if len(contratos) == 3 and '488/25' in contratos:
                        print(f"\n[!] PROBLEMA ENCONTRADO:")
                        print(f"    O cliente COMEXIM EUROPE tem 3 contratos: {contratos}")
                        print(f"    O diferencial_medio mostrado é: {cliente_data.get('diferencial_medio')}")
                        print(f"    Mas isso é a MÉDIA dos 3 contratos!")
                        print(f"    A IA não consegue distinguir qual contrato específico (488/25) tem qual diferencial!")

                    break

        except json.JSONDecodeError as e:
            print(f"[ERRO] Não conseguiu parsear JSON: {e}")
            print("\nPrimeiras 50 linhas do JSON:")
            for linha in json_lines[:50]:
                print(linha)

        print("\n3. ANÁLISE DO PROBLEMA:")
        print("=" * 80)
        print("O contrato 488/25 está agregado com outros 2 contratos do mesmo cliente (COMEXIM EUROPE).")
        print("Quando agregado por cliente, só mostramos:")
        print("  - diferencial_medio: média dos 3 contratos")
        print("  - contratos: ['488/25', '453/25A', '453/25B']")
        print("")
        print("A IA NÃO CONSEGUE saber o diferencial INDIVIDUAL do 488/25!")
        print("Ela só vê a média dos 3 contratos juntos.")
        print("")
        print("SOLUÇÃO NECESSÁRIA:")
        print("  Quando há UMA pergunta específica sobre UM contrato individual,")
        print("  a tool precisa retornar dados desagregados (linha por linha).")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_response()
