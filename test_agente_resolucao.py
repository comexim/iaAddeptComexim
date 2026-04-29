"""Testa resolução do campo codigo_agente_exportacao"""
import asyncio
import nest_asyncio
from app.utils.field_resolver import FieldResolver

nest_asyncio.apply()

fr = FieldResolver()

# Testa com descrição "BASKERVILLE"
codigo, nome, loja = asyncio.run(fr.resolve_field('codigo_agente_exportacao', 'BASKERVILLE', threshold=60))

print(f"Código retornado: {codigo}")
print(f"Nome retornado: {nome}")
print(f"Loja retornada: {loja}")

# Testa split do código
if codigo and ' ' in codigo:
    partes = codigo.split()
    print(f"\n✅ Split funcionou!")
    print(f"   Código do agente: {partes[0]}")
    print(f"   Loja do agente: {partes[1]}")
else:
    print(f"\n⚠️ Código não tem espaço para split: '{codigo}'")
