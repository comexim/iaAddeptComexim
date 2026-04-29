import asyncio
from app.utils.field_resolver import field_resolver

async def main():
    # Testa diferentes variações que o LLM pode ter usado
    test_cases = [
        "NET LANDED WEIGHT",
        "NET LANDED",
        "LANDED WEIGHT",
        "LANDED",
        "NET WEIGHT",
        "NDW",
        "NLW"
    ]
    
    print("Testando diferentes variações de 'NET LANDED WEIGHT'")
    print("=" * 70)
    
    for user_input in test_cases:
        print(f"\nInput: '{user_input}'")
        print("-" * 70)
        
        codigo, descricao, loja = await field_resolver.resolve_field(
            "condicao_peso", 
            user_input, 
            threshold=70  # Mesmo threshold do ada_tools
        )
        
        if codigo:
            print(f"✅ Resolvido: {codigo} - {descricao}")
        else:
            print(f"❌ Não resolvido (threshold: 70%)")

if __name__ == '__main__':
    asyncio.run(main())
