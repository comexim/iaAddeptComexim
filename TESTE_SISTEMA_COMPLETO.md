# Guia de Teste do Sistema Completo

## Pre-requisitos

Antes de iniciar os testes, certifique-se de que:

- [x] Upstash Redis configurado e credenciais no `.env`
- [x] OpenAI API key no `.env`
- [x] Evolution API configurada no `.env`
- [x] Supabase configurado com migração executada
- [x] SQL Server acessível
- [ ] ngrok instalado e configurado
- [ ] WhatsApp conectado na instância Evolution

## Fase 1: Testes Unitários (Sem WhatsApp)

### 1.1 Teste de Conexão Redis (Upstash)

```bash
python -m pip install redis
```

Crie `test_redis.py`:

```python
import asyncio
import os
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

async def test_redis():
    print("[INFO] Testando conexao com Upstash Redis...")

    client = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD"),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True
    )

    try:
        # Test PING
        pong = await client.ping()
        print(f"[OK] PING: {pong}")

        # Test SET/GET
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        print(f"[OK] SET/GET: {value}")

        # Test conversation memory pattern
        session_id = "5511999999999"
        await client.lpush(f"messages:{session_id}", "Mensagem de teste")
        await client.expire(f"messages:{session_id}", 7200)  # 2 horas

        messages = await client.lrange(f"messages:{session_id}", 0, -1)
        print(f"[OK] Memoria de conversa: {messages}")

        # Cleanup
        await client.delete("test_key")
        await client.delete(f"messages:{session_id}")

        print("\n[OK] Todos os testes Redis passaram!")

    except Exception as e:
        print(f"[ERRO] Falha no teste Redis: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_redis())
```

Execute:
```bash
python test_redis.py
```

**Resultado Esperado:**
```
[INFO] Testando conexao com Upstash Redis...
[OK] PING: True
[OK] SET/GET: test_value
[OK] Memoria de conversa: ['Mensagem de teste']

[OK] Todos os testes Redis passaram!
```

### 1.2 Teste do Sistema de Aprendizado de Preferências

```bash
python test_supabase.py
```

**Resultado Esperado:**
```
[OK] Teste 1: get_user_preferences passou
[OK] Teste 2: create_new_user passou
[OK] Teste 3: update_preference passou
[OK] Teste 4: learning_history passou
[OK] Teste 5: pre_loaded_users passou

[OK] Todos os testes Supabase passaram!
```

### 1.3 Teste de Detecção de Feedback

Crie `test_feedback_detection.py`:

```python
import asyncio
from app.services.preference_learning import PreferenceLearningService

async def test_feedback():
    service = PreferenceLearningService()

    test_cases = [
        ("diminua a mensagem", "nivel_detalhe", "resumido"),
        ("seja mais formal", "tom_de_voz", "profissional"),
        ("pode usar emojis", "emojis_habilitados", True),
        ("prefiro em bullet points", "formato_resposta", "bullet_points"),
    ]

    print("[INFO] Testando detecao de feedback...\n")

    for message, expected_field, expected_value in test_cases:
        feedbacks = await service.detect_feedback(message, "5511999999999")

        if feedbacks and feedbacks[0].field == expected_field:
            print(f"[OK] '{message}' -> {expected_field} = {expected_value}")
        else:
            print(f"[ERRO] '{message}' nao detectou {expected_field}")

    print("\n[OK] Teste de feedback concluido!")

if __name__ == "__main__":
    asyncio.run(test_feedback())
```

Execute:
```bash
python test_feedback_detection.py
```

### 1.4 Teste de Permissões

Crie `test_permissions.py`:

```python
from app.models.user import User, UserPermissions

def test_permissions():
    print("[INFO] Testando sistema de permissoes...\n")

    # Usuario com permissoes limitadas
    user = User(
        telefone="5511972390860",
        nome="Pedro Silva",
        email="pedro.silva@comexim.com.br",
        permissions=UserPermissions(direitos=["Financeiro", "Vendas"])
    )

    # Testes
    tests = [
        ("Financeiro", True),
        ("Vendas", True),
        ("Estoque", False),
        ("RH", False),
    ]

    for module, expected in tests:
        result = user.permissions.has_permission(module)
        status = "[OK]" if result == expected else "[ERRO]"
        print(f"{status} {user.nome} - {module}: {result} (esperado: {expected})")

    print("\n[OK] Teste de permissoes concluido!")

if __name__ == "__main__":
    test_permissions()
```

Execute:
```bash
python test_permissions.py
```

## Fase 2: Teste do Agente Orquestrador (Sem Webhook)

Crie `test_agent.py`:

```python
import asyncio
from app.agents.orchestrator import AgentOrchestrator
from app.models.user import User, UserPermissions

async def test_agent():
    print("[INFO] Testando agente orquestrador...\n")

    # Criar usuario de teste
    user = User(
        telefone="5511972390860",
        nome="Pedro Silva",
        email="pedro.silva@comexim.com.br",
        permissions=UserPermissions(direitos=["Financeiro", "Vendas", "Estoque"])
    )

    # Criar orquestrador
    orchestrator = AgentOrchestrator(session_id=user.telefone, user=user)

    # Teste 1: Consulta simples
    print("[TEST 1] Consulta de saldo bancario...")
    response = await orchestrator.process_message("Qual o saldo bancario atual?")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 2: Consulta com filtro
    print("[TEST 2] Consulta de vendas de dezembro...")
    response = await orchestrator.process_message("Mostre as vendas de dezembro de 2024")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 3: Feedback de preferencia
    print("[TEST 3] Feedback 'diminua a mensagem'...")
    response = await orchestrator.process_message("diminua a mensagem")
    print(f"Resposta: {response[:200]}...\n")

    # Teste 4: Verificar se preferencia foi aplicada
    print("[TEST 4] Nova consulta (deve ser mais curta)...")
    response = await orchestrator.process_message("Qual o estoque de produtos?")
    print(f"Resposta: {response[:200]}...\n")

    print("[OK] Testes do agente concluidos!")

if __name__ == "__main__":
    asyncio.run(test_agent())
```

Execute:
```bash
python test_agent.py
```

## Fase 3: Teste com Webhook (ngrok + Evolution API)

### 3.1 Configurar ngrok

1. Instalar ngrok:
   - Baixe em https://ngrok.com/download
   - Extraia e adicione ao PATH

2. Criar conta gratuita em https://ngrok.com

3. Autenticar:
```bash
ngrok config add-authtoken SEU_TOKEN_AQUI
```

4. Iniciar tunnel:
```bash
ngrok http 8000
```

**Resultado:**
```
Forwarding  https://a1b2c3d4.ngrok.io -> http://localhost:8000
```

Copie a URL `https://a1b2c3d4.ngrok.io`

### 3.2 Configurar Webhook na Evolution API

1. Acesse: https://evolutionv2.dev.automatexia.com.br/manager

2. Selecione instância `automatexteste2`

3. Vá em **Webhooks**

4. Configure:
   - **URL**: `https://a1b2c3d4.ngrok.io/webhook`
   - **Events**: Marque `messages.upsert`
   - **API Key**: `DE8E58E96A29-43D8-8A69-38A797102C36`

5. Salve

### 3.3 Iniciar o Sistema

```bash
python -m uvicorn app.main:app --reload
```

**Resultado Esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### 3.4 Verificar Logs em Tempo Real

Em outro terminal:
```bash
ngrok http 8000 --log=stdout
```

Isso mostrará todas as requisições recebidas.

## Fase 4: Teste via WhatsApp

### 4.1 Conectar WhatsApp na Evolution

1. Acesse: https://evolutionv2.dev.automatexia.com.br/manager
2. Instância `automatexteste2`
3. Clique em **Connect**
4. Escaneie QR Code com WhatsApp

### 4.2 Cenários de Teste

#### Teste 1: Consulta Básica
**Enviar:** "Qual o saldo bancário?"

**Esperado:**
- Sistema busca dados usando `IA_SaldoBancario()`
- Retorna lista de contas com saldos
- Resposta em formato médio (padrão)

#### Teste 2: Consulta com Filtro
**Enviar:** "Mostre as vendas dos últimos 7 dias"

**Esperado:**
- Sistema detecta período relativo
- Converte para datas (hoje - 7 dias até hoje)
- Busca usando `IA_Vendas(@DataInicio, @DataFim)`
- Retorna vendas do período

#### Teste 3: Consulta Sem Permissão
**Enviar:** "Mostre a folha de pagamento"

**Esperado:**
- Sistema verifica permissões do usuário
- Detecta que usuário não tem acesso a módulo RH
- Retorna mensagem educada informando falta de permissão

#### Teste 4: Aprendizado de Preferências
**Enviar:** "diminua a mensagem"

**Esperado:**
- Sistema detecta feedback sobre nível de detalhe
- Atualiza preferência para "resumido"
- Confirma: "Entendi! Vou enviar respostas mais curtas..."

**Enviar:** "Qual o estoque de produtos?"

**Esperado:**
- Resposta MUITO mais curta que a anterior
- Formato resumido aplicado automaticamente

#### Teste 5: Anti-Flood
**Enviar rapidamente:**
1. "oi"
2. "como"
3. "vai"

**Esperado:**
- Sistema acumula mensagens por 20 segundos
- Processa todas juntas: "oi como vai"
- Responde apenas uma vez

#### Teste 6: Múltiplos Feedbacks
**Enviar:** "seja mais formal e use bullet points"

**Esperado:**
- Detecta 2 feedbacks: tom_de_voz=profissional, formato_resposta=bullet_points
- Confirma ambas mudanças
- Próximas respostas usam tom formal + bullets

#### Teste 7: Consulta Complexa
**Enviar:** "Quais produtos estão com estoque abaixo de 100 unidades?"

**Esperado:**
- Agente usa ferramenta `consultar_estoque`
- Aplica filtro no resultado
- Retorna apenas produtos com estoque < 100

## Fase 5: Monitoramento

### 5.1 Logs do FastAPI

Monitorar terminal onde FastAPI está rodando:
```
INFO: 127.0.0.1 - "POST /webhook HTTP/1.1" 200 OK
```

### 5.2 Logs do Redis (Upstash Dashboard)

1. Acesse https://console.upstash.com/redis
2. Selecione seu banco
3. Clique em **CLI**
4. Execute:
```redis
KEYS *
```

Você verá:
```
1) "messages:5511972390860"
2) "antiflood:5511972390860"
```

Para ver conversas armazenadas:
```redis
LRANGE messages:5511972390860 0 -1
```

### 5.3 Logs do Supabase

1. Acesse https://dotybczrhvsyhcchxugu.supabase.co
2. Table Editor > `user_preferences`
3. Verifique atualizações em tempo real quando feedbacks forem detectados

Veja `learning_history` crescendo:
```json
[
  {
    "field": "nivel_detalhe",
    "old_value": "medio",
    "new_value": "resumido",
    "learned_from": "user_feedback",
    "confidence": 0.9,
    "timestamp": "2024-01-15T10:30:00Z"
  }
]
```

## Troubleshooting

### Webhook não recebe mensagens
1. Verificar se ngrok está rodando
2. Verificar se URL no Evolution API está correta
3. Testar webhook manualmente:
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"key": {"remoteJid": "5511999999999@s.whatsapp.net"}, "message": {"conversation": "teste"}}'
```

### Agente não responde
1. Verificar logs do FastAPI
2. Verificar se OpenAI API key está válida
3. Testar agente isoladamente com `test_agent.py`

### Preferências não são salvas
1. Verificar logs do Supabase (Table Editor > `preference_learning_log`)
2. Testar Supabase isoladamente com `test_supabase.py`
3. Verificar se `enable_preference_learning=True` no `.env`

### Redis não conecta
1. Verificar credenciais no `.env`
2. Testar com `test_redis.py`
3. Verificar Upstash dashboard se banco está ativo

## Checklist Final

- [ ] Redis (Upstash) funcionando (`test_redis.py` passou)
- [ ] Supabase funcionando (`test_supabase.py` passou)
- [ ] SQL Server funcionando (`test_connection.py` passou)
- [ ] Detecção de feedback funcionando (`test_feedback_detection.py` passou)
- [ ] Permissões funcionando (`test_permissions.py` passou)
- [ ] Agente orquestrador funcionando (`test_agent.py` passou)
- [ ] ngrok expondo webhook
- [ ] Webhook configurado na Evolution API
- [ ] WhatsApp conectado
- [ ] Teste via WhatsApp: consulta básica funcionou
- [ ] Teste via WhatsApp: aprendizado de preferências funcionou
- [ ] Teste via WhatsApp: anti-flood funcionou

## Próximos Passos Após Testes

Quando todos os testes passarem:

1. **Produção**: Substituir ngrok por servidor real (VPS, AWS, etc.)
2. **Monitoramento**: Adicionar logs estruturados (Sentry, CloudWatch)
3. **Backup**: Configurar backup automático do Supabase
4. **Escalabilidade**: Considerar Redis Cluster se usuários > 100
5. **Segurança**: Adicionar rate limiting por usuário
6. **Melhorias**: Coletar feedback dos diretores e ajustar prompts
