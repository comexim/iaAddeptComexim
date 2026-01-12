# Setup Upstash Redis (Sem Docker)

## Passo 1: Criar Conta Upstash (2 minutos)

1. Acesse: https://upstash.com/
2. Clique em **Sign Up**
3. Use Google ou GitHub para login rápido
4. Confirme email

## Passo 2: Criar Database Redis

1. No dashboard, clique **Create Database**
2. Configure:
   - **Name**: `agente-comexim`
   - **Type**: Regional
   - **Region**: Escolha o mais próximo (ex: São Paulo)
   - **Eviction**: No eviction
3. Clique **Create**

## Passo 3: Copiar Credenciais

Na página do database, você verá:

```
Endpoint: redis-12345.upstash.io
Port: 6379
Password: AaBbCcDd1234567890
```

Copie também a **REST URL** (opcional, para testes via HTTP).

## Passo 4: Atualizar .env

Edite o arquivo `.env` e substitua as linhas do Redis:

```env
# Redis (Upstash Cloud)
REDIS_HOST=redis-12345.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=AaBbCcDd1234567890
REDIS_DB=0
```

**IMPORTANTE**: Use suas credenciais reais do Upstash!

## Passo 5: Testar Conexão

Execute o teste:

```bash
python -c "from app.core.database import redis_client; print('Redis OK!' if redis_client.test_connection() else 'Redis FALHOU')"
```

Deve retornar: `Redis OK!`

## Passo 6: Iniciar Sistema

Agora você pode iniciar sem Docker:

```bash
python main.py
```

O sistema vai conectar automaticamente ao Upstash!

## Vantagens do Upstash

✅ **Gratuito**: 10.000 comandos/dia
✅ **Sem instalação**: Funciona direto na nuvem
✅ **Global**: Baixa latência
✅ **Persistente**: Dados não se perdem
✅ **TLS**: Conexão criptografada

## Monitorar Uso

No dashboard do Upstash você vê:
- Comandos executados
- Uso de memória
- Logs de conexão

## Limites do Plano Gratuito

- **10.000 comandos/dia** (suficiente para ~500 conversas)
- **256 MB** de dados
- **1 database**

Para produção com alto volume, considere upgrade ($0.20/100k comandos).

## Alternativa: Redis Labs

Se preferir outra opção:

1. Acesse: https://redis.com/try-free/
2. Crie conta
3. Configure database
4. Copie credenciais para `.env`

## Troubleshooting

### Erro: "Connection timeout"
**Solução**: Verifique se copiou host/password corretamente

### Erro: "Authentication failed"
**Solução**: Password errado - copie novamente do dashboard

### Erro: "Too many connections"
**Solução**: Upstash gratuito tem 100 conexões simultâneas - suficiente para testes

## Comparação: Docker vs Upstash

| Aspecto | Docker | Upstash |
|---------|--------|---------|
| Setup | Precisa Docker instalado | Só cadastro |
| Velocidade | Muito rápido (local) | Rápido (rede) |
| Persistência | Perde dados se parar | Dados sempre salvos |
| Custo | Grátis | Grátis (limite 10k/dia) |
| Deploy | Precisa Redis no servidor | Funciona anywhere |

**Para testes/desenvolvimento: Upstash é mais simples!**

---

Pronto! Com Upstash você não precisa de Docker ou instalação local. Tudo funciona na nuvem! ☁️
