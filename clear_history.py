"""Script para limpar histórico do cliente"""
import redis
import asyncio

async def clear_client_history():
    """Limpa histórico do cliente 35920000589"""
    redis_client = redis.Redis(
        host="redis-18430.c323.us-east-1-2.ec2.cloud.redislabs.com",
        port=18430,
        password="9pt9twxSRnsJn4Owfp4JIrKqz1e2k5If",
        db=0,
        decode_responses=True
    )

    # Busca TODAS as chaves para entender o padrão
    all_keys = redis_client.keys("*")
    print(f"Total de chaves no Redis: {len(all_keys)}")

    if all_keys:
        print("\nPrimeiras 20 chaves:")
        for key in all_keys[:20]:
            print(f"  - {key}")

    # Busca todas as chaves de histórico do cliente
    session_key = "35920000589_memory_comexim"
    keys = [k for k in all_keys if "35920000589" in k or "memory" in k]

    if keys:
        print(f"Encontradas {len(keys)} chaves:")
        for key in keys:
            print(f"  - {key}")

        # Deleta todas
        deleted = redis_client.delete(*keys)
        print(f"\n[OK] {deleted} chaves deletadas com sucesso!")
    else:
        print("[AVISO] Nenhuma chave encontrada")

    redis_client.close()

if __name__ == "__main__":
    asyncio.run(clear_client_history())
