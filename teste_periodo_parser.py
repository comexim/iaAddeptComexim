#!/usr/bin/env python3
"""
Teste do parser de período - verificar se "janeiro de 2026" está sendo parseado corretamente
"""
import sys
sys.path.insert(0, '/opt/agente-comexim-whatsapp')

from app.utils.date_parser import date_parser

print("="*80)
print("TESTE: Parser de período")
print("="*80)

testes = [
    "janeiro de 2026",
    "janeiro 2026",
    "2026/01",
    "01/2026",
    "fevereiro de 2026",
    "fevereiro 2026",
    "2026/02",
]

for periodo in testes:
    result = date_parser.parse_natural_date(periodo)
    print(f"\nEntrada: '{periodo}'")
    if result:
        print(f"  mes_embarque: {result.get('mes_embarque', 'N/A')}")
        print(f"  data_inicio: {result.get('data_inicio', 'N/A')}")
        print(f"  data_fim: {result.get('data_fim', 'N/A')}")
    else:
        print(f"  ERRO: Não conseguiu parsear!")

print("\n" + "="*80)
