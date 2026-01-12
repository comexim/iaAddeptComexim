"""
Teste de remoção de acentos
"""
import unicodedata
import re

def remove_accents(text: str) -> str:
    """Remove acentos de uma string usando normalização Unicode"""
    # Normaliza para NFD (decompõe caracteres com acentos)
    nfd = unicodedata.normalize('NFD', text)
    # Remove combining marks (acentos)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

# Testes
test_cases = [
    ("nestlé", "nestle"),
    ("Nestlé", "nestle"),
    ("NESTLÉ", "nestle"),
    ("café", "cafe"),
    ("São Paulo", "sao paulo"),
    ("MATIAS RUIZ & CIA SA", "matias ruiz & cia sa"),
]

print("Testando remoção de acentos:\n")
for input_text, expected_clean in test_cases:
    # Processa
    normalized = remove_accents(input_text.lower())
    normalized = re.sub(r'[^\w\s]', '', normalized).strip()
    normalized = re.sub(r'\s+', ' ', normalized)

    # Verifica
    status = "[OK]" if normalized == expected_clean else "[ERRO]"
    print(f"{status} '{input_text}' -> '{normalized}' (esperado: '{expected_clean}')")

# Teste de match
print("\n\nTeste de match Nestlé:")
query = "nestlé"
database_values = ["NESTLE ARARAS", "NESTLE BRASIL LTDA", "NESTRADE S.A.", "STARBUCKS COFFEE"]

query_normalized = remove_accents(query.lower())
query_normalized = re.sub(r'[^\w\s]', '', query_normalized).strip()
query_normalized = re.sub(r'\s+', ' ', query_normalized)

print(f"Query normalizada: '{query_normalized}'\n")

matches = []
for db_value in database_values:
    db_normalized = remove_accents(db_value.lower())
    db_normalized = re.sub(r'[^\w\s]', '', db_normalized).strip()
    db_normalized = re.sub(r'\s+', ' ', db_normalized)

    if query_normalized in db_normalized or db_normalized in query_normalized:
        matches.append(db_value)
        print(f"[MATCH] '{db_value}' (normalizado: '{db_normalized}')")
    else:
        print(f"[NO MATCH] '{db_value}' (normalizado: '{db_normalized}')")

print(f"\n\nTotal de matches: {len(matches)}")
print(f"Clientes encontrados: {matches}")
