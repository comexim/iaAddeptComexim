"""
Teste simples da API ADA (autenticação e teste de conexão)
"""
import asyncio
from app.core.ada_api_client import ada_api_client


async def test_api_ada():
    """Testa conexão e autenticação com API ADA"""
    print("\n" + "="*80)
    print("🔐 TESTE - AUTENTICAÇÃO API ADA")
    print("="*80 + "\n")
    
    try:
        print("1️⃣ Obtendo token de autenticação...")
        token = await ada_api_client.get_token()
        
        if token:
            print(f"✅ Token obtido com sucesso!")
            print(f"   Token (primeiros 50 chars): {token[:50]}...")
            print(f"   Tamanho: {len(token)} caracteres\n")
        else:
            print("❌ Falha ao obter token\n")
            return
        
        print("2️⃣ Testando conexão...")
        connected = await ada_api_client.test_connection()
        
        if connected:
            print("✅ Conexão estabelecida com sucesso!")
        else:
            print("❌ Falha na conexão")
        
        print("\n" + "="*80)
        print("✅ TESTE CONCLUÍDO!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_api_ada())
