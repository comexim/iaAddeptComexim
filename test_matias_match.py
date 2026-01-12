"""
Teste de matching MATIAS RUIZ
"""
import unicodedata
import re

def remove_accents(text: str) -> str:
    """Remove acentos de uma string usando normalização Unicode"""
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

# Simula o que vem da query do usuário (extraído pelo LLM)
user_query = "matias ruiz & cia sa"

# Simula o que está no banco de dados
database_values = [
    "MATIAS RUIZ & CIA.SA",
    "MATIAS RUIZ & CIA SA",
    "MATIAS RUIZ E CIA SA",
]

# Normaliza query
query_normalized = remove_accents(user_query.lower())
query_normalized = re.sub(r'[^\w\s]', ' ', query_normalized)  # substitui por espaço
query_normalized = re.sub(r'\s+', ' ', query_normalized).strip()

print(f"Query do usuário: '{user_query}'")
print(f"Query normalizada: '{query_normalized}'")
print()

for db_value in database_values:
    db_normalized = remove_accents(db_value.lower())
    db_normalized = re.sub(r'[^\w\s]', ' ', db_normalized)  # substitui por espaço
    db_normalized = re.sub(r'\s+', ' ', db_normalized).strip()

    # Testa match
    match = query_normalized in db_normalized or db_normalized in query_normalized

    status = "[MATCH]" if match else "[NO MATCH]"
    print(f"{status} DB: '{db_value}'")
    print(f"        DB normalizado: '{db_normalized}'")
    print(f"        Match? '{query_normalized}' in '{db_normalized}' = {query_normalized in db_normalized}")
    print()
