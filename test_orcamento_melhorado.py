"""
Valida: Melhorias no orçamento
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools

def test_orcamento():
    """Valida melhorias no orçamento"""
    print("=" * 80)
    print("VALIDACAO - Melhorias no orçamento")
    print("=" * 80)

    try:
        class FakeUser:
            phone_number = "test"
            nome = "Test User"
            telefone = "test"
            def has_permission(self, perm):
                return True

        sql_tools = SQLTools(user=FakeUser())

        # Teste 1: Pergunta geral sobre orçamento
        print("\n1. Pergunta geral: Qual o orçamento total de dezembro 2025?")
        print("-" * 80)
        sql_tools.user_query = "Qual o orçamento total de dezembro 2025?"
        result1 = sql_tools._pesquisa_orcamento(periodo="dezembro 2025")

        # Verifica totais gerais
        if "TOTAIS GERAIS" in result1:
            print("[OK] Seção TOTAIS GERAIS encontrada")

            # Extrai totais
            for linha in result1.split('\n'):
                if "Total Orçado" in linha or "Total Realizado" in linha or "Percentual Realizado" in linha:
                    print(f"  {linha}")
        else:
            print("[X] Seção TOTAIS GERAIS não encontrada")

        # Verifica novos campos
        print("\nVerificando novos campos (grupo, periodo, anos, meses):")
        if '"grupo"' in result1:
            print("[OK] Campo 'grupo' encontrado")
        else:
            print("[X] Campo 'grupo' NÃO encontrado")

        if '"periodo"' in result1:
            print("[OK] Campo 'periodo' encontrado")
        else:
            print("[X] Campo 'periodo' NÃO encontrado")

        if '"meses"' in result1:
            print("[OK] Campo 'meses' encontrado")
        else:
            print("[X] Campo 'meses' NÃO encontrado")

        # Teste 2: Pergunta sobre categoria específica
        print("\n\n2. Pergunta específica: Quanto gastamos com combustível em dezembro?")
        print("-" * 80)
        sql_tools.user_query = "Quanto gastamos com combustível em dezembro de 2025?"
        result2 = sql_tools._pesquisa_orcamento(periodo="dezembro 2025")

        # Verifica se filtrou
        if "categoria" in result2.lower():
            print("[INFO] Resultado tem categorias")

            # Procura COMBUSTIVEL
            if "COMBUSTIVEL" in result2.upper():
                print("[OK] Categoria COMBUSTIVEL encontrada")

                # Mostra linhas relevantes
                print("\nLinhas com COMBUSTIVEL:")
                for linha in result2.split('\n'):
                    if "COMBUSTI" in linha.upper():
                        print(f"  {linha[:120]}")
            else:
                print("[?] COMBUSTIVEL não encontrado (pode ter sido filtrado)")
        else:
            print("[X] Não encontrou categorias no resultado")

        # Teste 3: Verifica instruções
        print("\n\n3. Verificando instruções CRÍTICAS:")
        print("-" * 80)

        instrucoes_importantes = [
            "TOTAIS GERAIS (PRÉ-CALCULADOS)",
            "NÃO some manualmente",
            "saldo POSITIVO",
            "saldo NEGATIVO",
            "percentual > 100%",
        ]

        for instrucao in instrucoes_importantes:
            if instrucao in result1:
                print(f"[OK] Instrução '{instrucao}' encontrada")
            else:
                print(f"[X] Instrução '{instrucao}' NÃO encontrada")

        # Teste 4: Mostra exemplo de uma categoria
        print("\n\n4. Exemplo de categoria agregada:")
        print("-" * 80)

        linhas = result1.split('\n')
        in_json = False
        categoria_exemplo = []
        brace_count = 0

        for i, linha in enumerate(linhas):
            if '"categoria"' in linha and not in_json:
                in_json = True
                brace_count = 0
                categoria_exemplo = []

            if in_json:
                categoria_exemplo.append(linha)
                brace_count += linha.count('{') - linha.count('}')

                # Se fechou o objeto, para
                if brace_count <= 0 and len(categoria_exemplo) > 2:
                    break

        if categoria_exemplo:
            print("Primeira categoria agregada:")
            for linha in categoria_exemplo[:15]:
                print(linha)
        else:
            print("[X] Não conseguiu extrair exemplo de categoria")

        print("\n" + "=" * 80)
        print("[OK] VALIDACAO CONCLUIDA")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERRO] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_orcamento()
