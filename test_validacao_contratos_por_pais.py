"""
Valida: Seção CONTRATOS POR PAÍS nos resultados da tool
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_contratos_por_pais():
    """Valida se a tool retorna a seção CONTRATOS POR PAÍS"""
    print("=" * 80)
    print("VALIDACAO - Secao CONTRATOS POR PAIS")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())
        sql_tools.user_query = "quantas sacas de cafe foram exportadas em 12/2025?"

        print("\n1. Chamando a tool: _pesquisa_vendas(periodo='12/2025')")
        print("-" * 80)

        result = sql_tools._pesquisa_vendas(periodo="12/2025")

        print("\n2. Verificando se a secao CONTRATOS POR PAIS existe:")
        print("-" * 80)

        if "CONTRATOS POR PAÍS" in result or "CONTRATOS POR PAIS" in result:
            print("[OK] Secao CONTRATOS POR PAIS encontrada!")

            # Extrai a seção
            linhas = result.split('\n')
            in_section = False
            section_lines = []

            for linha in linhas:
                if "CONTRATOS POR PA" in linha.upper():
                    in_section = True
                    continue
                if in_section:
                    if linha.strip() == "" or "Dados agregados:" in linha:
                        break
                    section_lines.append(linha)

            print("\nConteudo da secao CONTRATOS POR PAIS:")
            print("-" * 80)
            for linha in section_lines[:30]:  # Primeiras 30 linhas
                print(linha)

            # Verifica se Argentina está lá
            section_text = "\n".join(section_lines)
            if "ARGENTINA" in section_text.upper():
                print("\n3. Verificando contratos da Argentina:")
                print("-" * 80)

                # Extrai linhas da Argentina (país e contratos estão em linhas diferentes)
                for i, linha in enumerate(section_lines):
                    if "ARGENTINA" in linha.upper():
                        print(linha)
                        # Pega também a próxima linha (onde estão os contratos)
                        if i + 1 < len(section_lines):
                            linha_contratos = section_lines[i + 1]
                            print(linha_contratos)

                            # Verifica se tem os 3 contratos (busca na linha de contratos E na linha do país)
                            texto_completo = linha + " " + linha_contratos
                            tem_513 = "513/25" in texto_completo
                            tem_558 = "558/25" in texto_completo
                            tem_559 = "559/25" in texto_completo

                            print("\nContratos encontrados:")
                            print(f"  513/25: {'SIM' if tem_513 else 'NAO'}")
                            print(f"  558/25: {'SIM' if tem_558 else 'NAO'}")
                            print(f"  559/25: {'SIM' if tem_559 else 'NAO'}")

                            if tem_513 and tem_558 and tem_559:
                                print("\n[OK] TODOS OS 3 CONTRATOS DA ARGENTINA ESTAO NA SECAO!")
                                print("     Agora a IA vai conseguir ver todos os contratos, mesmo de clientes diferentes!")
                            elif tem_558 and tem_559 and not tem_513:
                                print("\n[X] FALTOU o contrato 513/25!")
                            else:
                                print("\n[?] Situacao inesperada")

                        break
            else:
                print("\n[X] Argentina nao encontrada na secao CONTRATOS POR PAIS")

        else:
            print("[X] Secao CONTRATOS POR PAIS NAO encontrada!")
            print("\nPrimeiras 50 linhas do resultado:")
            print("-" * 80)
            for linha in result.split('\n')[:50]:
                print(linha)

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_contratos_por_pais()
