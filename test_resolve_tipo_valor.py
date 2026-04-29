import asyncio
from app.utils.field_resolver import field_resolver

async def main():
    test_cases = [
        "US$ KG",
        "DOLAR KG",
        "K",
        "CTS/LB",
        "C"
    ]
    
    print("Testando resolução de tipo_valor")
    print("=" * 70)
    
    for user_input in test_cases:
        print(f"\nInput: '{user_input}'")
        print("-" * 70)
        
        codigo, descricao, loja = await field_resolver.resolve_field(
            "tipo_valor", 
            user_input, 
            threshold=40
        )
        
        if codigo:
            print(f"✅ Resolvido: {codigo} - {descricao}")
        else:
            print(f"❌ Não resolvido (threshold: 40%)")

if __name__ == '__main__':
    asyncio.run(main())
