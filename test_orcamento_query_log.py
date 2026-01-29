"""
Script para simular query que a IA deve fazer para "janeiro 2026"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.date_parser import DateParser

def test_date_parse():
    """Testa parsing de 'janeiro 2026'"""
    print("=" * 80)
    print("TESTE DE PARSING - 'janeiro 2026'")
    print("=" * 80)

    texto = "janeiro 2026"
    print(f"\nTexto para parsear: '{texto}'")

    date_parser = DateParser()
    result = date_parser.parse_natural_date(texto)

    if result:
        print("\nResultado do parsing:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print("\n[ERRO] Nenhum resultado do parsing")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_date_parse()
