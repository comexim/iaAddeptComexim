import asyncio
from app.utils.field_resolver import field_resolver

async def main():
    user_input = "NET LANDED WEIGHT"
    
    print(f"Testando resolução de: '{user_input}'")
    print("=" * 60)
    
    codigo, descricao, loja = await field_resolver.resolve_field(
        "condicao_peso", 
        user_input, 
        threshold=70
    )
    
    print()
    print(f"Resultado:")
    print(f"  Código: {codigo}")
    print(f"  Descrição: {descricao}")
    print(f"  Loja: {loja}")

if __name__ == '__main__':
    asyncio.run(main())
