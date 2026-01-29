"""
Testa se o date_parser agora suporta ano completo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.date_parser import date_parser

def test_ano_completo():
    """Testa parsing de ano completo"""
    print("=" * 80)
    print("TESTE - PARSING DE ANO COMPLETO")
    print("=" * 80)

    # Testes de diferentes formas de especificar ano completo
    testes = [
        "2025 completo",
        "2025 inteiro",
        "ano 2025",
        "ano completo",
        "Orçamento de 2025 completo",
        "visão geral do ano 2025",
    ]

    for i, texto in enumerate(testes, 1):
        print(f"\n{i}. Teste: '{texto}'")
        print("-" * 80)

        result = date_parser.parse_natural_date(texto)

        if result:
            print(f"[OK] Parseado com sucesso!")
            print(f"  ano: {result.get('ano')}")
            print(f"  meses: {result.get('meses')}")
            print(f"  data_inicio: {result.get('data_inicio')}")
            print(f"  data_fim: {result.get('data_fim')}")
            print(f"  ano_completo: {result.get('ano_completo', False)}")

            # Validações
            if result.get('ano') == '2025' or result.get('ano') == str(2026):  # pode ser ano atual se não especificou
                print("  [OK] Ano correto")
            else:
                print(f"  [ERRO] Ano esperado: 2025, recebido: {result.get('ano')}")

            if result.get('meses') == ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']:
                print("  [OK] Todos os 12 meses incluídos")
            else:
                print(f"  [ERRO] Meses incorretos: {result.get('meses')}")

        else:
            print(f"[ERRO] Não foi possível parsear!")

    print("\n" + "=" * 80)
    print("TESTE CONCLUIDO")
    print("=" * 80)

if __name__ == "__main__":
    test_ano_completo()
