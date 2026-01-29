"""
Debug: Por que a IA interpretou errado a pergunta sobre Alemanha sem BL
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_debug():
    """Debug da resposta da tool"""
    print("=" * 80)
    print("DEBUG - Tool response para pergunta sobre Alemanha sem BL")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        print("\n1. Simulando a pergunta do usuário:")
        print("-" * 80)
        print("Pergunta: Dos contratos exportados para Alemanha em dezembro de 2025,")
        print("          quantos já foram embarcados mas ainda não têm BL?")

        sql_tools.user_query = "Dos contratos exportados para Alemanha em dezembro de 2025, quantos já foram embarcados mas ainda não têm BL?"

        print("\n2. Chamando _pesquisa_vendas(periodo='dezembro 2025'):")
        print("-" * 80)

        result = sql_tools._pesquisa_vendas(periodo="dezembro 2025")

        print("\n3. PROCURANDO SEÇÃO CONTRATOS POR PAÍS:")
        print("=" * 80)

        linhas = result.split('\n')

        # Procura seção CONTRATOS POR PAÍS
        in_section = False
        section_lines = []

        for i, linha in enumerate(linhas):
            if "CONTRATOS POR PA" in linha.upper():
                in_section = True
                print(f"\n[OK] Seção encontrada na linha {i}")
                continue

            if in_section:
                if "Dados agregados:" in linha:
                    break
                section_lines.append(linha)

        # Procura Alemanha
        print("\n4. INFORMAÇÕES DA ALEMANHA NA SEÇÃO:")
        print("-" * 80)

        for i, linha in enumerate(section_lines):
            if "ALEMAN" in linha.upper():
                print(f"\nLinha {i}: {linha}")
                # Mostra também a próxima linha (contratos)
                if i + 1 < len(section_lines):
                    print(f"Linha {i+1}: {section_lines[i+1]}")
                break

        print("\n5. PROCURANDO ALEMANHA NA AGREGAÇÃO POR CLIENTE:")
        print("=" * 80)

        # Procura no JSON agregado
        in_json = False
        json_lines = []
        brace_count = 0

        for linha in linhas:
            if "Dados agregados:" in linha:
                in_json = True
                continue

            if in_json:
                brace_count += linha.count('{') - linha.count('}')
                json_lines.append(linha)

                if brace_count <= 0 and len(json_lines) > 10:
                    break

        # Parse JSON
        import json
        try:
            json_text = '\n'.join(json_lines)
            dados = json.loads(json_text)

            # Procura clientes com país Alemanha
            for cliente_data in dados:
                paises = cliente_data.get("paises", [])
                if any("ALEMAN" in str(p).upper() for p in paises):
                    cliente = cliente_data.get("cliente", "")
                    print(f"\nCliente: {cliente}")
                    print(f"Países: {paises}")
                    print(f"Total contratos: {cliente_data.get('total_contratos')}")
                    print(f"Contratos com BL: {cliente_data.get('total_contratos_com_bl')}")
                    print(f"Contratos embarcados: {cliente_data.get('total_contratos_embarcados')}")
                    print(f"Lista contratos: {cliente_data.get('contratos', '')[:100]}")
                    print(f"Lista com BL: {cliente_data.get('contratos_com_bl', '')[:100]}")
                    print(f"Lista embarcados: {cliente_data.get('contratos_embarcados', '')[:100]}")

        except Exception as e:
            print(f"[ERRO ao parsear JSON] {e}")

        print("\n6. ANÁLISE DO PROBLEMA:")
        print("=" * 80)

        print("\nA IA viu as seguintes informações:")
        print("1. Seção CONTRATOS POR PAÍS:")
        print("   - ALEMANHA: 3 contrato(s), X sacas, Y cliente(s)")
        print("   - Lista de contratos: 488/25, 453/25A, 453/25B")
        print("")
        print("2. Dados agregados por cliente:")
        print("   - total_contratos: 3")
        print("   - total_contratos_com_bl: 3")
        print("   - total_contratos_embarcados: 3")
        print("")
        print("PERGUNTA: 'quantos já foram embarcados mas ainda não têm BL?'")
        print("")
        print("CÁLCULO CORRETO:")
        print("  embarcados SEM BL = embarcados - com_bl")
        print("  embarcados SEM BL = 3 - 3 = 0")
        print("")
        print("PROVÁVEL ERRO DA IA:")
        print("  A IA pode ter interpretado errado e contado:")
        print("  - total_contratos_embarcados (3)")
        print("  - Ou total_contratos_com_bl (3)")
        print("")
        print("  Em vez de calcular a DIFERENÇA (embarcados - com_bl)")

        print("\n7. VERIFICANDO INSTRUÇÕES:")
        print("=" * 80)

        # Procura instruções sobre "sem BL"
        instrucoes_sem_bl = False
        for i, linha in enumerate(linhas):
            if "SEM BL" in linha.upper() or "CONTRATOS SEM BL" in linha.upper():
                print(f"Linha {i}: {linha[:120]}")
                instrucoes_sem_bl = True

        if not instrucoes_sem_bl:
            print("\n[!] NÃO há instruções explícitas sobre como calcular 'sem BL'")
            print("    A IA precisa deduzir: sem_bl = total - com_bl")

        print("\n8. SOLUÇÃO NECESSÁRIA:")
        print("=" * 80)
        print("Adicionar instrução explícita:")
        print("  'Para calcular contratos SEM BL: total_contratos - total_contratos_com_bl'")
        print("  'Para calcular embarcados SEM BL: total_contratos_embarcados - total_contratos_com_bl'")

        print("\n" + "=" * 80)
        print("[OK] DEBUG CONCLUIDO")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_debug()
