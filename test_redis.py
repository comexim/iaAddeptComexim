import redis
import os
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv('REDIS_URL')
print(f'Testando conexao com Redis...')

try:
    client = redis.from_url(redis_url, decode_responses=True)
    result = client.ping()
    print(f'OK - Conexao bem-sucedida! PING: {result}')

    # Teste de escrita/leitura
    client.set('test_key', 'test_value')
    value = client.get('test_key')
    print(f'OK - Teste de escrita/leitura: {value}')
    client.delete('test_key')

except Exception as e:
    print(f'ERRO na conexao: {e}')

