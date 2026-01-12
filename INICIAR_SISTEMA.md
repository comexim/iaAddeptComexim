# Como Iniciar o Sistema - Agente Comexim IA

## Pré-requisitos

### 1. Iniciar Redis (Obrigatório)

O sistema precisa do Redis para memória de conversação. Escolha uma opção:

#### Opção A: Redis via Docker (Recomendado)
```bash
docker run -d --name redis-comexim -p 6379:6379 redis:alpine
```

#### Opção B: Redis via WSL (Windows)
```bash
# No WSL/Ubuntu
sudo apt update
sudo apt install redis-server -y
sudo service redis-server start

# Testar
redis-cli ping
# Deve retornar: PONG
```

#### Opção C: Redis Cloud (Upstash/Redis Cloud)
1. Crie conta gratuita em https://upstash.com
2. Crie banco Redis
3. Atualize `.env`:
   ```env
   REDIS_HOST=sua-instancia.upstash.io
   REDIS_PORT=6379
   REDIS_PASSWORD=sua-senha
   ```

### 2. Verificar Configurações

Execute para validar:
```bash
python -c "from app.core.config import settings; print('✓ Config carregada')"
```

## Iniciar o Sistema

### Método 1: Script Automático (Recomendado)
```bash
python main.py
```

### Método 2: Com Auto-Reload (Desenvolvimento)
```bash
uvicorn main:app --reload --port 8000
```

### Método 3: Via run.bat
```bash
run.bat
```

## Verificar se Está Funcionando

### 1. Health Check
Abra no navegador:
```
http://localhost:8000/health
```

Deve retornar:
```json
{
  "status": "healthy",
  "sql_server": "connected",
  "redis": "connected",
  "supabase": "connected"
}
```

### 2. Endpoint Raiz
```
http://localhost:8000/
```

Deve retornar:
```json
{
  "service": "Agente Comexim IA",
  "version": "1.0.0",
  "status": "running"
}
```

## Configurar Webhook na Evolution API

### 1. Acesse Evolution API
URL: https://evolutionv2.dev.automatexia.com.br/

### 2. Configure Webhook
- **Instância**: automatexteste2
- **Webhook URL**: `http://SEU_IP:8000/webhook/evolution`
- **Events**:
  - `messages.upsert` ✓
  - `messages.update` ✓

### 3. Headers do Webhook
```json
{
  "x-evolution-token": "DE8E58E96A29-43D8-8A69-38A797102C36"
}
```

## Testar o Sistema

### Teste 1: Envie mensagem via WhatsApp
1. Conecte instância `automatexteste2` ao seu WhatsApp
2. Envie: "Olá"
3. Sistema deve responder via WhatsApp

### Teste 2: Consulta SQL
1. Envie: "Quanto temos em caixa?"
2. Sistema deve consultar IA_SaldoBancario() e responder

### Teste 3: Aprendizado de Preferências
1. Envie: "Quanto temos em estoque?"
2. Sistema responde (formato médio)
3. Envie: "diminua a mensagem"
4. Sistema detecta e atualiza preferência
5. Próxima resposta será muito mais curta!

## Logs em Tempo Real

```bash
# Ver logs do sistema
tail -f agente-comexim.log

# Ou no console (se rodou com python main.py)
# Logs aparecem direto no terminal
```

## Configurações Atuais

✅ SQL Server: 200.221.173.187:6776 (Protheus)
✅ Supabase: https://dotybczrhvsyhcchxugu.supabase.co
✅ OpenAI: GPT-4o configurado
✅ Evolution API: https://evolutionv2.dev.automatexia.com.br
✅ Instância: automatexteste2
✅ Sistema de Aprendizado: HABILITADO

## Troubleshooting

### Erro: "Connection refused" (Redis)
**Solução**: Inicie Redis com uma das opções acima

### Erro: "OPENAI_API_KEY not found"
**Solução**: Verifique `.env` - chave já está configurada

### Erro: "Cannot connect to SQL Server"
**Solução**: Execute `python test_connection.py` para diagnosticar

### Erro: "Supabase error"
**Solução**: Execute `python test_supabase.py` para diagnosticar

### Webhook não recebe mensagens
**Solução**:
1. Verifique se sistema está rodando: `http://localhost:8000/health`
2. Use ngrok para expor localhost:
   ```bash
   ngrok http 8000
   # Use URL do ngrok no webhook
   ```

## Estrutura de Endpoints

```
GET  /                          # Info da API
GET  /health                    # Health check
POST /webhook/evolution         # Webhook WhatsApp
POST /api/message               # Enviar mensagem manual
GET  /api/preferences/{phone}   # Ver preferências de usuário
```

## Parar o Sistema

```bash
# Se rodou com python main.py
Ctrl + C

# Se rodou como serviço
# (depende do método de deploy)
```

## Próximos Passos

Após testar localmente:
1. Configure firewall para liberar porta 8000
2. Configure domínio/SSL (Let's Encrypt)
3. Use supervisor/systemd para rodar como serviço
4. Configure monitoramento (logs, alertas)
5. Backup automático do Supabase

---

**Sistema pronto para teste! 🚀**

Qualquer dúvida, consulte:
- [PROXIMOS_PASSOS.md](PROXIMOS_PASSOS.md)
- [docs/SISTEMA_APRENDIZADO.md](docs/SISTEMA_APRENDIZADO.md)
- [TESTE_COMPLETO.md](TESTE_COMPLETO.md)
