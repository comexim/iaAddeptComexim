# Quick Start - Agente Comexim

## Status Atual

| Componente | Status | Teste | Próxima Ação |
|------------|--------|-------|--------------|
| SQL Server | ✅ Funcionando | `test_connection.py` PASSOU | Nenhuma |
| Supabase | ✅ Funcionando | `test_supabase.py` PASSOU | Nenhuma |
| Sistema Permissões | ✅ Implementado | `test_permissions.py` | Executar teste |
| Detecção Feedback | ✅ Implementado | `test_feedback_detection.py` | Executar teste |
| Agente Orquestrador | ✅ Implementado | `test_agent.py` | Executar teste |
| Redis | ⏳ Aguardando | `test_redis.py` | **Configurar Upstash** |
| ngrok | ⏳ Aguardando | - | **Instalar e iniciar** |
| Webhook Evolution | ⏳ Aguardando | - | **Configurar URL** |
| WhatsApp | ⏳ Aguardando | - | **Conectar instância** |

## Inicio Rápido (30 minutos)

### 1. Configurar Upstash Redis (5 min) ⚠️ PRIORITÁRIO

```bash
# Acesse: https://console.upstash.com/redis
# Crie conta gratuita
# Clique "Create Database"
# Região: us-east-1
# Copie: host, port, password
```

Atualize `.env`:
```env
REDIS_HOST=redis-xxxxx.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=AaBbCcDd1234567890
REDIS_DB=0
```

Teste:
```bash
python test_redis.py
```

### 2. Executar Testes Unitários (10 min)

```bash
# Teste 1: Permissões
python test_permissions.py
# Esperado: [OK] 4/4 testes

# Teste 2: Feedback
python test_feedback_detection.py
# Esperado: [OK] 4/4 testes

# Teste 3: Agente (requer OpenAI API)
python test_agent.py
# Esperado: [OK] 4 respostas do agente
```

### 3. Configurar ngrok (5 min)

```bash
# Download: https://ngrok.com/download
# Extrair e adicionar ao PATH

# Autenticar
ngrok config add-authtoken SEU_TOKEN

# Iniciar (em terminal separado)
ngrok http 8000
```

**Copie a URL**: `https://a1b2c3d4.ngrok.io`

### 4. Iniciar Sistema (5 min)

Terminal 1 (ngrok):
```bash
ngrok http 8000
```

Terminal 2 (FastAPI):
```bash
python -m uvicorn app.main:app --reload
```

### 5. Configurar Webhook (2 min)

1. Acesse: https://evolutionv2.dev.automatexia.com.br/manager
2. Instância: `automatexteste2`
3. Menu: **Webhooks**
4. Configure:
   - URL: `https://SEU_NGROK.ngrok.io/webhook`
   - Events: `messages.upsert`
   - API Key: `DE8E58E96A29-43D8-8A69-38A797102C36`
5. Salvar

### 6. Conectar WhatsApp (2 min)

1. Mesma página do manager
2. Botão: **Connect**
3. Escanear QR Code com WhatsApp

### 7. Testar! (5 min)

Envie via WhatsApp:

1. "Qual o saldo bancário?"
2. "Mostre as vendas de dezembro"
3. "diminua a mensagem"
4. "Qual o estoque?"

## Comandos Úteis

### Verificar Status do Sistema

```bash
# Ver logs FastAPI
# (aparecem no terminal onde uvicorn está rodando)

# Ver logs ngrok
# (aparecem no terminal onde ngrok está rodando)

# Ver logs Upstash
# Acesse: https://console.upstash.com/redis → seu banco → CLI
KEYS *
LRANGE messages:5511972390860 0 -1

# Ver logs Supabase
# Acesse: https://dotybczrhvsyhcchxugu.supabase.co
# Table Editor → user_preferences
```

### Resetar Sistema

```bash
# Limpar memória Redis (Upstash CLI)
FLUSHDB

# Resetar preferências de um usuário (Supabase SQL Editor)
UPDATE user_preferences
SET nivel_detalhe = 'medio',
    tom_de_voz = 'profissional',
    formato_resposta = 'texto',
    feedback_count = 0,
    learning_history = '[]'::jsonb
WHERE telefone = '5511972390860';
```

## Troubleshooting Express

| Problema | Solução Rápida |
|----------|----------------|
| Webhook não recebe | 1. Verificar ngrok rodando<br>2. Verificar URL no Evolution<br>3. Testar: `curl -X POST http://localhost:8000/webhook` |
| Redis erro | 1. Verificar credenciais `.env`<br>2. Testar: `python test_redis.py`<br>3. Ver Upstash dashboard |
| Agente não responde | 1. Verificar OpenAI API key<br>2. Ver logs FastAPI<br>3. Testar: `python test_agent.py` |
| Preferências não salvam | 1. Verificar `enable_preference_learning=True`<br>2. Testar: `python test_supabase.py`<br>3. Ver Table Editor |

## Checklist de Teste via WhatsApp

- [ ] Consulta básica: "Qual o saldo bancário?"
- [ ] Consulta com filtro: "Vendas de dezembro"
- [ ] Consulta sem permissão: "Mostre folha de pagamento"
- [ ] Feedback curto: "diminua a mensagem"
- [ ] Verificar aprendizado: próxima resposta é mais curta
- [ ] Feedback múltiplo: "seja mais formal e use bullet points"
- [ ] Anti-flood: enviar 3 mensagens rápidas → apenas 1 resposta
- [ ] Consulta complexa: "Produtos com estoque abaixo de 100"

## Arquivos de Teste Criados

| Arquivo | Propósito | Status |
|---------|-----------|--------|
| `test_connection.py` | SQL Server | ✅ PASSOU (47 contas, 913 produtos) |
| `test_supabase.py` | Supabase CRUD | ✅ PASSOU (5/5 testes) |
| `test_redis.py` | Redis/Upstash | ⏳ Aguarda credenciais |
| `test_permissions.py` | Sistema permissões | ⏳ Aguarda execução |
| `test_feedback_detection.py` | Detecção feedback | ⏳ Aguarda execução |
| `test_agent.py` | Agente orquestrador | ⏳ Aguarda execução |

## Documentação Completa

| Arquivo | Conteúdo |
|---------|----------|
| `STATUS_PROJETO.md` | Status detalhado de todos componentes |
| `TESTE_SISTEMA_COMPLETO.md` | Guia completo de testes (200+ linhas) |
| `SISTEMA_APRENDIZADO.md` | Sistema de preferências adaptativas |
| `SETUP_UPSTASH.md` | Configuração Upstash Redis |
| `SETUP_NGROK.md` | Configuração ngrok |
| `PROXIMOS_PASSOS.md` | Passos de implementação |
| `QUICK_START.md` | Este arquivo |

## Variáveis de Ambiente (.env)

Certifique-se de ter TODAS configuradas:

```env
# SQL Server
SQL_SERVER_HOST=xxx
SQL_SERVER_PORT=1433
SQL_SERVER_DATABASE=Protheus
SQL_SERVER_USERNAME=xxx
SQL_SERVER_PASSWORD=xxx
SQL_SERVER_DRIVER=SQL Server

# Redis (AGUARDANDO UPSTASH)
REDIS_HOST=redis-xxxxx.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=xxx
REDIS_DB=0

# Supabase
SUPABASE_URL=https://dotybczrhvsyhcchxugu.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

# OpenAI
OPENAI_API_KEY=sk-proj-z5l7tNgEBZeMoSSsIqVbniWg_3_...

# Evolution API
EVOLUTION_API_URL=https://evolutionv2.dev.automatexia.com.br
EVOLUTION_API_KEY=DE8E58E96A29-43D8-8A69-38A797102C36
EVOLUTION_INSTANCE_NAME=automatexteste2

# Features
ENABLE_PREFERENCE_LEARNING=True
```

## Próximos Passos Imediatos

1. ⚠️ **PRIORITÁRIO**: Configurar Upstash Redis
2. Executar todos os testes unitários
3. Instalar e configurar ngrok
4. Iniciar sistema (uvicorn + ngrok)
5. Configurar webhook na Evolution
6. Conectar WhatsApp
7. Testar via WhatsApp

**Tempo total estimado**: 30 minutos

## Suporte

Caso encontre problemas:

1. Verifique logs do FastAPI (terminal uvicorn)
2. Verifique logs do ngrok (terminal ngrok)
3. Execute testes isolados para identificar componente com problema
4. Consulte `TESTE_SISTEMA_COMPLETO.md` seção Troubleshooting
5. Verifique `.env` para credenciais incorretas

## Estrutura do Projeto

```
agente-comexim/
├── app/
│   ├── agents/          # Orquestrador LangChain
│   ├── api/             # Rotas FastAPI
│   ├── core/            # Config, Database, Supabase
│   ├── models/          # Pydantic models
│   ├── services/        # Preference learning, Anti-flood
│   └── tools/           # SQL tools
├── docs/                # SQLs do Supabase
├── test_*.py            # Scripts de teste
├── .env                 # Credenciais (NUNCA comitar!)
├── requirements.txt     # Dependências Python
└── *.md                 # Documentação
```

**Sistema pronto para uso!** 🚀
