# Setup com Ngrok - Agente Comexim IA

## Passo 1: Instalar Ngrok

### Windows (Chocolatey)
```bash
choco install ngrok
```

### Ou Download Direto
1. Acesse: https://ngrok.com/download
2. Baixe para Windows
3. Extraia `ngrok.exe` em `C:\ngrok\`
4. Adicione ao PATH

## Passo 2: Criar Conta Ngrok (Gratuita)

1. Acesse: https://dashboard.ngrok.com/signup
2. Crie conta (Google/GitHub)
3. Copie seu authtoken

## Passo 3: Configurar Authtoken

```bash
ngrok config add-authtoken SEU_TOKEN_AQUI
```

## Passo 4: Iniciar Redis

```bash
# Docker (Recomendado)
docker run -d --name redis-comexim -p 6379:6379 redis:alpine

# Verificar
docker ps | findstr redis
```

## Passo 5: Iniciar Sistema Python

```bash
# Terminal 1: Sistema
python main.py
```

Aguarde até ver:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

## Passo 6: Iniciar Ngrok

```bash
# Terminal 2: Ngrok
ngrok http 8000
```

Você verá algo como:
```
Session Status    online
Forwarding        https://abc123.ngrok-free.app -> http://localhost:8000
```

**Copie a URL**: `https://abc123.ngrok-free.app`

## Passo 7: Configurar Webhook na Evolution API

### 7.1 Acesse Evolution API
URL: https://evolutionv2.dev.automatexia.com.br/

### 7.2 Configure Webhook
- **Instância**: automatexteste2
- **Webhook URL**: `https://abc123.ngrok-free.app/webhook/evolution`
- **Events**: ✓ messages.upsert
- **Enabled**: ✓ Ativo

### 7.3 Headers (se necessário)
```json
{
  "apikey": "DE8E58E96A29-43D8-8A69-38A797102C36"
}
```

## Passo 8: Testar

### 8.1 Health Check
Abra no navegador:
```
https://abc123.ngrok-free.app/health
```

Deve retornar:
```json
{
  "status": "healthy",
  "sql_server": "connected",
  "redis": "connected"
}
```

### 8.2 Teste via WhatsApp
1. Conecte WhatsApp à instância `automatexteste2`
2. Envie: "Olá"
3. Sistema deve responder

### 8.3 Monitore Logs
No terminal do Python, você verá:
```
[INFO] Webhook recebido de +5511999999999
[INFO] Processando mensagem: Olá
[INFO] Resposta gerada: Olá! Como posso...
```

## Comandos Úteis

### Reiniciar Redis
```bash
docker restart redis-comexim
```

### Ver Logs Redis
```bash
docker logs redis-comexim
```

### Parar Tudo
```bash
# Parar sistema Python
Ctrl + C (no terminal 1)

# Parar ngrok
Ctrl + C (no terminal 2)

# Parar Redis
docker stop redis-comexim
```

### Limpar Dados Redis
```bash
docker exec -it redis-comexim redis-cli FLUSHALL
```

## Troubleshooting

### Ngrok: "Session Expired"
**Solução**: Versão gratuita expira em 2h. Reinicie:
```bash
Ctrl + C
ngrok http 8000
# Nova URL gerada - atualize webhook
```

### Ngrok: "Too Many Connections"
**Solução**: Versão gratuita tem limite. Considere upgrade ou use outra ferramenta.

### Sistema não recebe webhooks
1. Verifique URL ngrok está correta no webhook
2. Teste manualmente:
   ```bash
   curl https://abc123.ngrok-free.app/health
   ```
3. Verifique logs do ngrok (terminal 2)
4. Verifique logs do sistema (terminal 1)

### Redis Connection Failed
```bash
# Verificar se está rodando
docker ps | findstr redis

# Se não estiver, iniciar
docker start redis-comexim
```

## Alternativa: Ngrok Config File

Crie `ngrok.yml` para configurações persistentes:

```yaml
version: "2"
authtoken: SEU_TOKEN_AQUI
tunnels:
  agente-comexim:
    proto: http
    addr: 8000
    subdomain: agente-comexim  # Requer plano pago
```

Iniciar com config:
```bash
ngrok start agente-comexim
```

## Plano Gratuito vs Pago

### Gratuito (Atual)
- ✓ 1 túnel simultâneo
- ✓ HTTPS automático
- ✗ URL aleatória (muda a cada restart)
- ✗ Sessão expira em 2h
- ✗ 40 requisições/minuto

### Pago ($10/mês)
- ✓ 3 túneis simultâneos
- ✓ Subdomínio fixo
- ✓ Sem limite de tempo
- ✓ 120 requisições/minuto

**Para testes, gratuito é suficiente!**

## Checklist Final

- [ ] Ngrok instalado e configurado
- [ ] Redis rodando (Docker)
- [ ] Sistema Python iniciado (porta 8000)
- [ ] Ngrok expondo localhost:8000
- [ ] Webhook configurado na Evolution API
- [ ] WhatsApp conectado à instância
- [ ] Teste enviado e recebido

---

**Pronto! Sistema exposto e funcionando! 🚀**
