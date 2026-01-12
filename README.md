# Agente IA Comexim - ERP via WhatsApp

Sistema de Inteligência Artificial para acesso ao ERP Protheus via WhatsApp com aprendizado adaptativo de preferências dos usuários.

## Status do Projeto

✅ **95% Completo - Pronto para Testes**

## Principais Funcionalidades

- **Consultas em Linguagem Natural**: "Qual o saldo bancário?" → Consulta SQL automática
- **Aprendizado Adaptativo**: IA aprende automaticamente preferências de cada usuário
- **Permissões Granulares**: 8 módulos (Financeiro, Vendas, Estoque, etc.) com controle de acesso
- **Anti-Flood**: Agrupa mensagens rápidas em uma única consulta
- **Memória Conversacional**: Lembra contexto das últimas 10 mensagens
- **Segurança**: Proteção SQL Injection, validação de permissões, rate limiting
- **Transcrição de Áudio**: Suporte a mensagens de voz via Whisper (OpenAI)
- **Integração WhatsApp**: Evolution API v2

## Estrutura do Projeto

```
agente-comexim/
├── app/
│   ├── agents/
│   │   └── orchestrator.py        # Orquestrador LangChain
│   ├── api/
│   │   ├── webhook.py             # Endpoint WhatsApp
│   │   └── auth.py                # Autenticação
│   ├── core/
│   │   ├── config.py              # Configurações
│   │   ├── database.py            # SQL Server client
│   │   └── supabase_client.py     # Supabase client
│   ├── models/
│   │   ├── user.py                # User, Permissions
│   │   ├── preferences.py         # UserPreferences
│   │   └── message.py             # WhatsAppMessage
│   ├── services/
│   │   ├── preference_learning.py # Sistema de aprendizado
│   │   ├── anti_flood.py          # Buffer anti-flood
│   │   └── date_parser.py         # Parser de datas PT-BR
│   ├── tools/
│   │   └── sql_tools.py           # Tools LangChain SQL
│   └── main.py                    # FastAPI app
├── docs/
│   ├── supabase_setup.sql         # Schema Supabase
│   └── supabase_migration.sql     # Migração (usado)
├── test_*.py                      # Scripts de teste
├── check_dependencies.py          # Verificador de deps
├── requirements.txt               # Dependências Python
├── .env                           # Credenciais (NUNCA comitar!)
├── .env.example                   # Template de .env
├── QUICK_START.md                 # Guia rápido
├── STATUS_PROJETO.md              # Status detalhado
├── TESTE_SISTEMA_COMPLETO.md      # Guia de testes
├── SISTEMA_APRENDIZADO.md         # Doc. aprendizado
├── APRESENTACAO_CLIENTE.md        # Apresentação executiva
└── README.md                      # Este arquivo
```

## Inicio Rápido

```bash
# 1. Verificar dependências
python check_dependencies.py

# 2. Instalar dependências (se necessário)
python -m pip install -r requirements.txt

# 3. Configurar .env (ver seção abaixo)

# 4. Executar testes
python test_connection.py    # SQL Server
python test_supabase.py       # Supabase
python test_redis.py          # Redis (após configurar Upstash)
python test_agent.py          # Agente IA

# 5. Iniciar sistema
python -m uvicorn app.main:app --reload
```

## Configuração .env

```env
# SQL Server (Protheus)
SQL_SERVER_HOST=seu_host
SQL_SERVER_PORT=1433
SQL_SERVER_DATABASE=Protheus
SQL_SERVER_USERNAME=seu_usuario
SQL_SERVER_PASSWORD=sua_senha
SQL_SERVER_DRIVER=SQL Server

# Redis (Upstash - ver SETUP_UPSTASH.md)
REDIS_HOST=redis-xxxxx.upstash.io
REDIS_PORT=6379
REDIS_PASSWORD=sua_senha_upstash
REDIS_DB=0

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=sua_chave_anon
SUPABASE_SERVICE_ROLE_KEY=sua_chave_service

# OpenAI
OPENAI_API_KEY=sk-proj-xxxxx

# Evolution API
EVOLUTION_API_URL=https://evolutionv2.dev.automatexia.com.br
EVOLUTION_API_KEY=sua_chave_api
EVOLUTION_INSTANCE_NAME=nome_instancia

# Features
ENABLE_PREFERENCE_LEARNING=True
```

## Documentação Completa

| Arquivo | Propósito |
|---------|-----------|
| [QUICK_START.md](QUICK_START.md) | Início rápido em 30 minutos |
| [STATUS_PROJETO.md](STATUS_PROJETO.md) | Status de todos componentes |
| [TESTE_SISTEMA_COMPLETO.md](TESTE_SISTEMA_COMPLETO.md) | Guia completo de testes |
| [SISTEMA_APRENDIZADO.md](docs/SISTEMA_APRENDIZADO.md) | Sistema de preferências |
| [SETUP_UPSTASH.md](SETUP_UPSTASH.md) | Configuração Redis cloud |
| [SETUP_NGROK.md](SETUP_NGROK.md) | Configuração ngrok |
| [APRESENTACAO_CLIENTE.md](APRESENTACAO_CLIENTE.md) | Apresentação executiva |

## Testes

### Unitários
```bash
python test_connection.py         # SQL Server
python test_supabase.py           # Supabase CRUD
python test_redis.py              # Redis/Upstash
python test_permissions.py        # Sistema de permissões
python test_feedback_detection.py # Detecção de feedback
python test_agent.py              # Agente orquestrador
```

### Integração (via WhatsApp)
Ver [TESTE_SISTEMA_COMPLETO.md](TESTE_SISTEMA_COMPLETO.md)

## Módulos Disponíveis

1. **Financeiro**: Saldo bancário, contas pagas, contas a pagar
2. **Vendas**: Vendas por período, clientes, produtos
3. **Estoque**: Produtos, quantidades, movimentações
4. **Compras**: Compras por período, fornecedores
5. **Orçamento**: Orçamentos disponíveis e executados
6. **RH**: Folha de pagamento (em desenvolvimento)
7. **Fiscal**: Notas fiscais (em desenvolvimento)
8. **Contábil**: Relatórios contábeis (em desenvolvimento)

## Usuários Pré-configurados

| Nome | Telefone | Módulos |
|------|----------|---------|
| Pedro Silva | 5511972390860 | Financeiro, Vendas, Estoque, Compras, Orçamento |
| Robson Junior | 5511997073363 | Financeiro, Vendas, Estoque, Compras, Orçamento |
| Rodrigo A. | 5511971051313 | Financeiro, Vendas, Estoque, Compras, Orçamento, RH, Fiscal |
| Raul Marques | 5511961146063 | Todos |
| Rafaela Ribeiro | 5511979302077 | Financeiro, Vendas |

## Tecnologias

- **Python 3.10+**
- **FastAPI** - Web framework
- **LangChain/LangGraph** - Framework de IA
- **OpenAI GPT-4o** - Modelo de linguagem
- **SQL Server** - Database (Protheus)
- **Supabase** - Database (preferências)
- **Redis** - Cache e memória
- **Evolution API** - WhatsApp integration
- **Pydantic** - Validação de dados

## Custos Operacionais

- **OpenAI**: R$ 50-250/mês (variável por uso)
- **Supabase**: R$ 0 (free tier até 500MB)
- **Upstash Redis**: R$ 0 (free tier 10k cmds/dia)
- **Evolution API**: R$ 0 (auto-hospedado)
- **Total**: R$ 50-250/mês

## Próximos Passos

1. **Configurar Upstash Redis** (5 min) - Ver [SETUP_UPSTASH.md](SETUP_UPSTASH.md)
2. **Executar testes** (10 min) - Ver seção Testes acima
3. **Configurar ngrok** (5 min) - Ver [SETUP_NGROK.md](SETUP_NGROK.md)
4. **Iniciar sistema** (1 min) - `uvicorn app.main:app --reload`
5. **Conectar WhatsApp** (2 min) - Evolution API manager
6. **Testar via WhatsApp** (5 min) - Ver [TESTE_SISTEMA_COMPLETO.md](TESTE_SISTEMA_COMPLETO.md)

## Troubleshooting

### Redis não conecta
```bash
# Verificar credenciais no .env
# Testar: python test_redis.py
# Ver dashboard: https://console.upstash.com/redis
```

### Webhook não recebe mensagens
```bash
# 1. Verificar ngrok rodando
# 2. Verificar URL configurada no Evolution
# 3. Testar manualmente:
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"key": {"remoteJid": "5511999999999@s.whatsapp.net"}, "message": {"conversation": "teste"}}'
```

### Agente não responde
```bash
# 1. Verificar OpenAI API key no .env
# 2. Ver logs FastAPI (terminal uvicorn)
# 3. Testar isoladamente: python test_agent.py
```

## Segurança

- ✅ Autenticação por API Key
- ✅ Validação de permissões por módulo
- ✅ Proteção SQL Injection
- ✅ Rate limiting (anti-flood)
- ✅ WHERE clause obrigatório (tabelas grandes)
- ✅ Timeout em consultas longas
- ✅ Credenciais em .env (nunca em código)
- ✅ Logs de auditoria

## Licença

Propriedade da Comexim. Todos os direitos reservados.

---

**Desenvolvido com Claude Sonnet 4.5** | Janeiro 2025 | v1.0.0
