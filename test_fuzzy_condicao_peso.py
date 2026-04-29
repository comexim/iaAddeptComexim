from rapidfuzz import fuzz
import unicodedata

def normalize_text(text: str) -> str:
    """Normaliza texto"""
    nfd = unicodedata.normalize('NFD', text)
    without_accents = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    normalized = without_accents.replace('$', ' ').replace('/', ' ').replace('-', ' ')
    return ' '.join(normalized.lower().split())

# Dados da API
opcoes = [
    {"codigo": "NDW", "descricao": "NET DELIVERED WEIGHT"},
    {"codigo": "NLW", "descricao": "NET LANDED WEIGHT"},
    {"codigo": "NSW", "descricao": "NET SHIPPED WEIGHT"},
    {"codigo": "RWT", "descricao": "REWEIGHTS"},
    {"codigo": "WWT", "descricao": "WARRANT WEIGHT"}
]

# Input do usuário
user_input = "NET LANDED WEIGHT"
normalized_input = normalize_text(user_input)

print(f"Input normalizado: '{normalized_input}'")
print()

# Testa fuzzy matching
for opcao in opcoes:
    desc_normalized = normalize_text(opcao['descricao'])
    codigo_normalized = normalize_text(opcao['codigo'])
    
    # Testa match exato de descrição
    if desc_normalized == normalized_input:
        print(f"✅ EXACT MATCH - Descrição: '{opcao['descricao']}' (codigo: {opcao['codigo']})")
        continue
    
    # Testa match exato de código
    if codigo_normalized == normalized_input:
        print(f"✅ EXACT MATCH - Código: '{opcao['codigo']}' (descricao: {opcao['descricao']})")
        continue
    
    # Fuzzy matching
    ratio_desc = fuzz.ratio(normalized_input, desc_normalized)
    ratio_code = fuzz.ratio(normalized_input, codigo_normalized)
    token_desc = fuzz.token_set_ratio(normalized_input, desc_normalized)
    
    print(f"Código: {opcao['codigo']:<5} | Descrição: {opcao['descricao']:<25}")
    print(f"  ratio_desc: {ratio_desc:.1f}% | ratio_code: {ratio_code:.1f}% | token_set: {token_desc:.1f}%")
