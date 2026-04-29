"""Testa resolução do campo tipoComissao"""
import asyncio
import nest_asyncio
from app.utils.field_resolver import FieldResolver

nest_asyncio.apply()

fr = FieldResolver()

# Testa com descrição "CTS/LIB" (ou parte dela)
test_values = ["LIB", "CTS/LIB", "SACA DE 50", "S50", "50 KG"]

print("=" * 70)
print("TESTE DE RESOLUÇÃO: tipoComissao")
print("=" * 70)
print()

for valor in test_values:
    print(f"🔍 Testando: '{valor}'")
    codigo, descricao, loja = asyncio.run(
        fr.resolve_field('tipo_comissao', valor, threshold=60)
    )
    
    if codigo:
        print(f"   ✅ Código: {codigo}")
        print(f"   ✅ Descrição: {descricao}")
    else:
        print(f"   ❌ Não resolvido")
    print()

print("=" * 70)
