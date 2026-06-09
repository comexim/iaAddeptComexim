# Manual Técnico — Agente Comexim IA

Sistema de consulta ao ERP Protheus via WhatsApp, com agente de IA (LangGraph + OpenAI).

---

## Índice

1. [Visão Geral da Arquitetura](#1-visão-geral-da-arquitetura)
2. [Estrutura de Pastas](#2-estrutura-de-pastas)
3. [Fluxo Completo de uma Mensagem](#3-fluxo-completo-de-uma-mensagem)
4. [Configuração do Ambiente (.env)](#4-configuração-do-ambiente-env)
5. [Como Subir o Projeto](#5-como-subir-o-projeto)
6. [Deploy em Produção (Linux/systemd)](#6-deploy-em-produção-linuxsystemd)
7. [Banco de Dados — SQL Server (Protheus)](#7-banco-de-dados--sql-server-protheus)
8. [Redis — Cache e Memória](#8-redis--cache-e-memória)
9. [Supabase — Agendamentos e Preferências](#9-supabase--agendamentos-e-preferências)
10. [Autenticação de Usuários](#10-autenticação-de-usuários)
11. [Agente IA — Como Funciona](#11-agente-ia--como-funciona)
12. [Tools Disponíveis](#12-tools-disponíveis)
13. [Scheduler de Relatórios Agendados](#13-scheduler-de-relatórios-agendados)
14. [Anti-Flood e Buffer de Mensagens](#14-anti-flood-e-buffer-de-mensagens)
15. [Permissões de Usuário](#15-permissões-de-usuário)
16. [O que NÃO Fazer — Armadilhas Conhecidas](#16-o-que-não-fazer--armadilhas-conhecidas)
17. [Como Criar um Ambiente de Teste](#17-como-criar-um-ambiente-de-teste)
18. [Logs e Monitoramento](#18-logs-e-monitoramento)

---

## 1. Visão Geral da Arquitetura

```
WhatsApp (usuário)
      │
      ▼
UAZAPI (intermediário WhatsApp)
      │ POST /webhook
      ▼
FastAPI (main.py)
      │
      ├─► Autenticação (Protheus API)
      ├─► Anti-flood (Redis)
      ├─► Transcrição de áudio (OpenAI Whisper) — se for áudio
      │
      ▼
AgentOrchestrator (LangGraph)
      │
      ├─► SQL Tools → SQL Server (Protheus) — consultas
      └─► ADA Tools → API ADA — criação de contratos
      │
      ▼
ResponseFormatter → WhatsApp (resposta)
```

**Tecnologias principais:**

| Componente | Tecnologia |
|---|---|
| API Web | FastAPI + Uvicorn |
| Agente IA | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Banco ERP | SQL Server (Protheus) via pyodbc |
| Cache/Memória | Redis |
| Agendamentos | Supabase (PostgreSQL) |
| WhatsApp | UAZAPI |
| Transcrição | OpenAI Whisper |
| Envio de email | SMTP Gmail |

---

## 2. Estrutura de Pastas

```
agente-comexim/
├── main.py                        # Inicialização FastAPI + scheduler
├── requirements.txt               # Dependências Python
├── .env                           # Variáveis de ambiente (não vai pro git)
├── .env.example                   # Template do .env
│
├── app/
│   ├── api/
│   │   └── webhook.py             # Endpoint POST /webhook (entrada de mensagens)
│   │
│   ├── agents/
│   │   ├── orchestrator.py        # Orquestrador principal (LangGraph)
│   │   ├── sql_tools.py           # Tools de consulta SQL (30+ tools)
│   │   └── ada_tools.py           # Tools de criação de contratos (API ADA)
│   │
│   ├── core/
│   │   ├── config.py              # Configurações centralizadas (Pydantic Settings)
│   │   ├── database.py            # SQLServerClient — executa queries no Protheus
│   │   ├── redis_client.py        # Cliente Redis (cache, memória, anti-flood)
│   │   ├── supabase_client.py     # Cliente Supabase (agendamentos, preferências)
│   │   └── ada_api_client.py      # Cliente HTTP da API ADA (contratos)
│   │
│   ├── models/
│   │   ├── user.py                # UserPermissions, ProtheusAuthResponse
│   │   ├── message.py             # WhatsAppMessage, parser de webhook
│   │   ├── preferences.py         # UserPreferences (aprendizado)
│   │   └── contrato_ada.py        # Modelos de contrato de venda/exportação
│   │
│   ├── prompts/
│   │   └── system_prompt.py       # System prompt dinâmico com dados do usuário
│   │
│   ├── services/
│   │   ├── auth.py                # Autenticação via Protheus API
│   │   ├── whatsapp.py            # Envio de mensagens WhatsApp via UAZAPI
│   │   ├── formatter.py           # Divide respostas longas em múltiplas mensagens
│   │   ├── audio.py               # Download e transcrição de áudio (Whisper)
│   │   ├── email.py               # Envio de emails com anexo xlsx
│   │   ├── scheduler.py           # Jobs de relatórios agendados (APScheduler)
│   │   └── preference_learning.py # Aprende preferências do usuário
│   │
│   └── utils/
│       ├── date_parser.py         # Parser de datas em linguagem natural
│       ├── sql_validator.py       # Validação de segurança das queries
│       └── field_resolver.py      # Resolve campos de contrato (fuzzy match)
```

---

## 3. Fluxo Completo de uma Mensagem

### Passo a passo detalhado:

**1. Webhook recebe a mensagem** (`app/api/webhook.py`)
- UAZAPI faz POST para `/webhook`
- O webhook parseia o payload (formato UAZAPI)
- Extrai: número do telefone, texto, tipo (texto ou áudio)
- Ignora mensagens enviadas pelo próprio bot (`fromMe: true`)
- Agenda `process_message_flow()` como background task (retorna 200 imediatamente ao UAZAPI)

**2. Anti-flood** (`app/core/redis_client.py`)
- Mensagem entra num buffer Redis com chave `buffer:{telefone}`
- Sistema aguarda `ANTI_FLOOD_WAIT_SECONDS` (padrão: 20s)
- Se novas mensagens chegarem no período, acumula tudo
- Processa apenas quando o usuário para de digitar
- Isso evita responder no meio de uma sequência de mensagens

**3. Autenticação** (`app/services/auth.py`)
- Consulta cache Redis: chave `user:{telefone}`
- Se não estiver em cache, chama `POST {PROTHEUS_API_URL}/iaProtheus/getToken`
- Protheus retorna nome, email e lista de permissões
- Resultado fica em cache por `REDIS_MEMORY_TTL` segundos (padrão: 2h)
- Se não autorizado, responde "Usuário não autorizado" e para

**4. Transcrição de áudio** (`app/services/audio.py`) — *só se for áudio*
- Baixa o arquivo via UAZAPI
- Envia para OpenAI Whisper
- Retorna texto transcrito que segue o fluxo normal

**5. Orquestração** (`app/agents/orchestrator.py`)
- Carrega histórico de mensagens do Redis (últimas `REDIS_MEMORY_WINDOW * 2` mensagens)
- Detecta se é fluxo de criação de contrato (ADA) ou consulta normal
- Monta system prompt com dados do usuário (nome, permissões, data atual)
- Cria agente LangGraph (react pattern) com as tools disponíveis
- Chama OpenAI com todo o contexto
- A IA decide qual tool chamar baseado na pergunta

**6. Execução das tools** (`app/agents/sql_tools.py`)
- Tool chamada executa `sql_client.execute_function(nome_da_função, filtros)`
- `database.py` monta e executa `SELECT * FROM dbo.NomeFuncao(params)`
- Resultado volta como lista de dicionários
- A IA interpreta e gera a resposta em linguagem natural

**7. Formatação e envio** (`app/services/formatter.py` + `app/services/whatsapp.py`)
- Se `ENABLE_RESPONSE_FORMATTER=true`: divide resposta longa em múltiplas mensagens
- Envia cada parte com delay de `MESSAGE_DELAY_SECONDS` entre elas
- Chama `POST {EVOLUTION_API_URL}/send/text` do UAZAPI

**8. Memória**
- Mensagem do usuário e resposta da IA são salvas no Redis
- Chave: `memory:{session_id}` com TTL de `REDIS_MEMORY_TTL`

---

## 4. Configuração do Ambiente (.env)

Copie `.env.example` para `.env` e preencha:

```env
# APPLICATION
APP_NAME=agente-comexim
ENV=production          # development ou production
DEBUG=false
LOG_LEVEL=INFO          # DEBUG para ver mais detalhes

# SQL SERVER (Protheus)
SQL_SERVER_HOST=ip_ou_hostname_do_servidor
SQL_SERVER_PORT=6776
SQL_SERVER_DATABASE=nome_do_banco
SQL_SERVER_USER=usuario_sql
SQL_SERVER_PASSWORD=senha_sql
SQL_SERVER_DRIVER=ODBC Driver 17 for SQL Server   # precisa estar instalado no servidor

# REDIS
REDIS_HOST=redis-xxxxx.redislabs.com
REDIS_PORT=18430
REDIS_PASSWORD=senha_redis
REDIS_DB=0

# PROTHEUS API (autenticação de usuários)
PROTHEUS_API_URL=http://ip_protheus:porta
PROTHEUS_API_TOKEN_ENDPOINT=/iaProtheus/getToken

# UAZAPI (WhatsApp)
EVOLUTION_API_URL=https://sua_instancia.uazapi.com
EVOLUTION_API_TOKEN=token_uazapi
EVOLUTION_INSTANCE_NAME=nome_da_instancia

# OPENAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...
AI_MODEL=gpt-4o
AI_TEMPERATURE=0.3
AI_MAX_TOKENS=4000
FORMATTER_MODEL=gpt-4o-mini
FORMATTER_TEMPERATURE=0

# MEMÓRIA
REDIS_MEMORY_TTL=7200        # segundos que o histórico fica no Redis (2h)
REDIS_MEMORY_WINDOW=10       # quantas trocas (user+AI) ficam no contexto

# ANTI-FLOOD
ANTI_FLOOD_WAIT_SECONDS=20   # aguarda 20s para acumular mensagens
MESSAGE_DELAY_SECONDS=3      # delay entre partes de resposta longa

# SUPABASE
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# EMAIL (SMTP Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=email@gmail.com
SMTP_PASSWORD=senha_de_app_gmail

# FEATURES (ligar/desligar funcionalidades)
ENABLE_AUDIO_TRANSCRIPTION=true
ENABLE_RESPONSE_FORMATTER=false
ENABLE_IMAGE_ANALYSIS=false
ENABLE_PREFERENCE_LEARNING=true
```

### Observações importantes sobre o .env:

- `SQL_SERVER_DRIVER` precisa corresponder ao driver ODBC instalado no servidor. Verifique com `odbcinst -q -d` (Linux)
- `SMTP_PASSWORD` para Gmail é uma **senha de aplicativo**, não a senha da conta. Gerar em: Conta Google → Segurança → Senhas de app
- `REDIS_MEMORY_WINDOW=10` significa que as últimas 10 perguntas + 10 respostas ficam em contexto. Aumentar demais estoura o limite de tokens da OpenAI
- `ANTI_FLOOD_WAIT_SECONDS=20` é o tempo que o sistema aguarda antes de processar. Se o usuário mandar 3 mensagens em 20s, elas são concatenadas e processadas de uma vez

---

## 5. Como Subir o Projeto

### Pré-requisitos

```bash
# Python 3.12+
python3 --version

# ODBC Driver para SQL Server (Linux)
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update
ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev
```

### Instalação

```bash
# Clonar o repositório
git clone https://github.com/Pedroax/agente-comexim-whatsapp.git
cd agente-comexim-whatsapp

# Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
nano .env  # preencher com os valores reais
```

### Rodar localmente

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

O `--reload` reinicia automaticamente quando o código muda. **Não usar em produção.**

### Verificar se subiu

```bash
curl http://localhost:8000/
# deve retornar {"status": "ok"} ou similar
```

---

## 6. Deploy em Produção (Linux/systemd)

### Arquivo de serviço

O serviço está configurado em `/etc/systemd/system/agente-comexim.service`.

### Comandos essenciais

```bash
# Ver status
systemctl status agente-comexim

# Reiniciar (após git pull)
systemctl restart agente-comexim

# Ver logs em tempo real
journalctl -u agente-comexim -f

# Ver últimas 50 linhas de log
journalctl -u agente-comexim -n 50 --no-pager

# Ver logs de um período específico (horário UTC)
journalctl -u agente-comexim --since "2026-05-29 10:00" --until "2026-05-29 11:00" --no-pager
```

### Processo de deploy

```bash
cd /opt/agente-comexim-whatsapp

# Atualizar código
git fetch origin
git reset --hard origin/main   # garante que os arquivos locais ficam iguais ao remoto

# Reiniciar serviço
systemctl restart agente-comexim

# Confirmar que subiu sem erros
journalctl -u agente-comexim -n 20 --no-pager
```

> **Atenção:** `git pull` às vezes diz "Already up to date" mesmo depois de buscar novos commits, se o branch local estiver em estado divergente. Por isso usar sempre `git fetch origin && git reset --hard origin/main`.

---

## 7. Banco de Dados — SQL Server (Protheus)

### Como as queries funcionam

O sistema **nunca** escreve no banco. Todas as consultas são `SELECT * FROM stored_function()`.

O arquivo `app/core/database.py` tem a classe `SQLServerClient` com o método `execute_function()`:

```python
sql_client.execute_function("dbo.IA_Vendas", filters={"mesEmbarque": "202601"})
# Gera: SELECT * FROM dbo.IA_Vendas() WHERE mesEmbarque = '202601'

sql_client.execute_function("dbo.IA_VendasPar", filters={"data_inicio": "20260101", "data_fim": "20260131"})
# Gera: SELECT * FROM dbo.IA_VendasPar('20260101', '20260131')
```

### Distinção entre funções com e sem parâmetros

Funções sem parâmetros (`IA_Vendas`, `IA_Compras`, etc.) retornam todos os dados e os filtros são aplicados como cláusula `WHERE` pelo Python.

Funções `Par` (`IA_VendasPar`, `IA_ContasAPagarPar`, etc.) recebem parâmetros diretamente na chamada SQL.

Isso está mapeado no dicionário `FUNCTION_PARAMETERS` dentro de `database.py`:

```python
FUNCTION_PARAMETERS = {
    "IA_Vendas": [],                          # sem parâmetros → WHERE
    "IA_VendasPar": ["data_inicio", "data_fim"],  # com parâmetros → na chamada
    "IA_Cotacao_Par": ["data"],               # com parâmetro de data
    ...
}
```

### Adicionar uma nova função

1. Criar a stored function no SQL Server
2. Adicionar entrada em `FUNCTION_PARAMETERS` em `database.py`
3. Criar a tool correspondente em `sql_tools.py`
4. Adicionar a tool na lista `get_tools()` de `sql_tools.py`

---

## 8. Redis — Cache e Memória

### O que fica no Redis

| Chave | Conteúdo | TTL |
|---|---|---|
| `user:{telefone}` | Dados do usuário autenticado | `REDIS_MEMORY_TTL` (2h) |
| `memory:{session_id}` | Histórico de mensagens | `REDIS_MEMORY_TTL` (2h) |
| `buffer:{telefone}` | Buffer anti-flood | 60s |
| `scheduler_result:{telefone}` | Último resultado de query (para xlsx) | 300s |
| `contrato_pendente:{session_id}` | Estado de criação de contrato em andamento | 3600s |
| `ultimo_contrato:{session_id}` | Último contrato consultado (contexto) | 3600s |

### Conexão Redis

O Redis é acessado de forma assíncrona. A reconexão é automática se a conexão cair.

Se ver no log:
```
Conexão Redis perdida: Event loop is closed. Reconectando...
Reconexão Redis bem-sucedida
```
Isso é normal — o cliente reconecta automaticamente.

---

## 9. Supabase — Agendamentos e Preferências

### Tabelas usadas

**`relatorios_agendados`** — relatórios automáticos configurados pelos usuários

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | uuid | ID do agendamento |
| `telefone` | text | Telefone do usuário |
| `descricao` | text | O que o relatório deve gerar |
| `frequencia` | text | `diario`, `semanal`, `mensal` ou `unico` |
| `horario` | text | `HH:MM` |
| `dia_semana` | int | 0=segunda ... 6=domingo (para semanal) |
| `dia_mes` | int | 1-31 (para mensal) |
| `canal` | text | `whatsapp`, `email` ou `ambos` |
| `email_destino` | text | Email de destino (opcional) |
| `next_run` | timestamptz | Próxima execução |
| `last_run` | timestamptz | Última execução |
| `status` | text | `ativo` ou `cancelado` |

**`user_preferences`** — preferências aprendidas de cada usuário (tom, formato, emojis, etc.)

**`preference_learning_log`** — histórico de aprendizado de preferências

### Constraint importante

A coluna `frequencia` tem um CHECK constraint que só aceita valores válidos. Se precisar adicionar nova frequência, rodar no SQL Editor do Supabase:

```sql
ALTER TABLE relatorios_agendados DROP CONSTRAINT relatorios_agendados_frequencia_check;
ALTER TABLE relatorios_agendados ADD CONSTRAINT relatorios_agendados_frequencia_check
  CHECK (frequencia IN ('diario', 'semanal', 'mensal', 'unico'));
```

---

## 10. Autenticação de Usuários

### Fluxo normal

1. Usuário manda mensagem pelo WhatsApp
2. Sistema extrai o telefone (sem o prefixo 55)
3. Consulta `POST {PROTHEUS_API_URL}/iaProtheus/getToken` com `{"telefone": "13991234567"}`
4. Protheus retorna dados do usuário e lista de permissões
5. Resultado fica em cache no Redis por 2h

### Bypass (hardcoded)

Alguns usuários estão configurados diretamente em `app/services/auth.py` para não depender da API do Protheus. Isso é útil para testes e para usuários que a API não retorna corretamente.

Para adicionar um novo usuário no bypass:

```python
if phone == "11999999999":
    return UserPermissions(
        telefone="11999999999",
        nome="Nome do Usuário",
        email="email@comexim.com.br",
        direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
    )
```

### Permissões disponíveis

`Financeiro`, `Estoque`, `Vendas`, `Compras`, `Orçamento`, `RH`, `Fiscal`, `Contábil`

Cada tool verifica se o usuário tem a permissão necessária antes de executar.

---

## 11. Agente IA — Como Funciona

### Pattern usado: ReAct (Reason + Act)

O agente usa LangGraph com o pattern ReAct:
1. Recebe a mensagem do usuário
2. Raciocina sobre qual tool usar
3. Executa a tool
4. Analisa o resultado
5. Decide se precisa de mais tools ou se já tem a resposta
6. Retorna a resposta final

### System prompt

O system prompt é gerado dinamicamente em `app/prompts/system_prompt.py` com:
- Nome e permissões do usuário
- Data e hora atual
- Instruções de comportamento
- Lista de tools disponíveis e quando usar cada uma

### Histórico de conversa

O histórico fica no Redis e é carregado a cada mensagem. Limite configurável por `REDIS_MEMORY_WINDOW`. Quando o histórico fica muito grande, apenas as últimas N trocas são enviadas para a OpenAI (janela deslizante).

### Rate limit OpenAI

O sistema tem retry automático em caso de erro 429 (rate limit):
- Aguarda 10 segundos e tenta novamente
- Se falhar novamente, retorna mensagem de erro ao usuário

Se o erro for `insufficient_quota` (crédito zerado), **não há retry** — precisa adicionar crédito na conta OpenAI em [platform.openai.com/billing](https://platform.openai.com/billing).

---

## 12. Tools Disponíveis

Todas as tools estão em `app/agents/sql_tools.py`. A IA escolhe qual usar baseada na pergunta do usuário.

| Tool | Função SQL | Permissão | Descrição |
|---|---|---|---|
| `pesquisa_vendas` | `IA_Vendas` / `IA_VendasPar` | Vendas | Contratos de venda/exportação |
| `pesquisa_compras` | `IA_Compras` / `IA_ComprasPar` | Compras | Contratos de compra |
| `pesquisa_contas_a_pagar` | `IA_ContasAPagar` / `IA_ContasAPagarPar` | Financeiro | Contas a pagar |
| `pesquisa_contas_pagas` | `IA_ContasPagas` / `IA_ContasPagasPar` | Financeiro | Contas já pagas |
| `pesquisa_contas_a_receber` | `IA_ContasAReceber` / `IA_ContasAReceberPar` | Financeiro | Contas a receber |
| `pesquisa_saldo_bancario` | `IA_SaldoBancario` | Financeiro | Saldo por banco/moeda |
| `pesquisa_estoque` | `IA_Estoque` | Estoque | Estoque físico de café |
| `pesquisa_cotacao` | `IA_Cotacao_Par` | Vendas | Cotações (dólar, euro, café, futuros) |
| `pesquisa_orcamento` | `IA_Orcamento` / `IA_OrcamentoPar` | Financeiro | Orçamento vs realizado |
| `pesquisa_despesa_venda` | `IA_DespesaVenda` | Vendas | Despesas por contrato |
| `pesquisa_longshort` | `IA_LongShort` | Vendas | Posição long/short |
| `pesquisa_internet` | Tavily API | — | Busca na internet (fallback) |
| `criar_relatorio_agendado` | Supabase | — | Agenda relatório recorrente ou único |
| `listar_relatorios_agendados` | Supabase | — | Lista agendamentos ativos |
| `cancelar_relatorio_agendado` | Supabase | — | Cancela agendamento por ID |
| `cancelar_todos_relatorios_agendados` | Supabase | — | Cancela todos os agendamentos |
| `criar_contrato_venda` | API ADA | Vendas | Cria contrato de exportação |

### Como a tool `pesquisa_cotacao` funciona

Chama `SELECT * FROM dbo.IA_Cotacao_Par('YYYYMMDD')`. Se o usuário não informar data, usa o dia atual.

Parâmetros:
- `data`: data desejada (qualquer formato, converte automaticamente para YYYYMMDD)
- `tipo`: filtro por tipo (`"Dolar"`, `"Euro"`, `"Café"`, `"Dólar Comercial"`)
- `ativo`: filtro por instrumento (`"DOLZ26"`, `"KCK6"`, etc.)

Campos disponíveis no retorno: `COTACAO`, `AJUSTE`, `ABERTURA`, `FECHAMENTO`, `SITUACAO`, `tipo`, `ativo`.

---

## 13. Scheduler de Relatórios Agendados

### Como funciona

O APScheduler roda um job **toda hora no minuto 0** que:
1. Busca no Supabase todos os relatórios com `next_run <= agora` e `status = 'ativo'`
2. Para cada relatório, autentica o usuário e executa a consulta via agente IA
3. Envia o resultado pelo canal configurado (`whatsapp`, `email` ou `ambos`)
4. Se for `frequencia = 'unico'`: cancela o agendamento após enviar
5. Se for recorrente: atualiza `next_run` para a próxima execução

### Frequências suportadas

| Frequência | Descrição |
|---|---|
| `diario` | Todos os dias no horário definido |
| `semanal` | Uma vez por semana no dia/horário definido |
| `mensal` | Uma vez por mês no dia/horário definido |
| `unico` | Uma única vez no horário definido, depois cancela automaticamente |

### Email com anexo xlsx

Quando o canal inclui email, o sistema:
1. Salva o resultado bruto da query no Redis (chave `scheduler_result:{telefone}`)
2. Após envio, lê do Redis e gera um arquivo `.xlsx` com `openpyxl`
3. Envia o xlsx como anexo no email

---

## 14. Anti-Flood e Buffer de Mensagens

O sistema implementa um buffer para lidar com usuários que mandam várias mensagens em sequência rápida.

**Como funciona:**
1. Mensagem chega → entra no buffer Redis (`buffer:{telefone}`)
2. Sistema aguarda `ANTI_FLOOD_WAIT_SECONDS` (padrão 20s)
3. Se novas mensagens chegarem, o timer reinicia
4. Quando o usuário para de digitar por 20s, todas as mensagens são concatenadas e processadas juntas

**Configuração:** `ANTI_FLOOD_WAIT_SECONDS=20` no `.env`

---

## 15. Permissões de Usuário

Cada tool verifica a permissão antes de executar. Se o usuário não tiver a permissão, recebe uma mensagem explicando que não tem acesso.

**Mapeamento de permissões:**

| Permissão | Tools liberadas |
|---|---|
| `Financeiro` | contas_a_pagar, contas_pagas, contas_a_receber, saldo_bancario, orcamento |
| `Vendas` | vendas, cotacao, despesa_venda, longshort, criar_contrato |
| `Compras` | compras |
| `Estoque` | estoque |
| `Orçamento` | orcamento |

---

## 16. O que NÃO Fazer — Armadilhas Conhecidas

### Git no servidor

**Não usar** `git pull` diretamente se o branch local puder estar divergente. Sempre usar:
```bash
git fetch origin && git reset --hard origin/main
```

### Redis e event loop

O `_salvar_resultado_scheduler` usa `ThreadPoolExecutor` para rodar coroutines de dentro de código síncrono. Isso é necessário porque as tools do LangChain rodam em contexto síncrono mas o Redis é assíncrono.

**Não tentar** trocar por `asyncio.ensure_future()` ou `loop.run_until_complete()` diretamente — vai dar erro de "event loop já rodando" ou "Future attached to different loop".

### Contexto de tokens OpenAI

Não aumentar `REDIS_MEMORY_WINDOW` para muito além de 15. Com GPT-4o e histórico longo (especialmente se tiver resultados de queries grandes), é fácil estourar os 30.000 TPM do plano básico.

### ODBC Driver

O driver `ODBC Driver 17 for SQL Server` precisa estar instalado no servidor Linux. Se mudar o servidor ou subir em nova máquina, isso é o primeiro passo que esquece.

Verificar com:
```bash
odbcinst -q -d
```

### .env não pode ir pro git

O `.env` está no `.gitignore`. Se acidentalmente commitar com credenciais, trocar todas as senhas imediatamente.

### Supabase CHECK constraint

A coluna `frequencia` tem constraint que limita os valores aceitos. Se criar uma nova frequência no código sem atualizar o constraint no Supabase, vai dar erro 400 silencioso ao tentar criar agendamento.

### Crédito OpenAI

O erro `insufficient_quota` (diferente de rate limit) significa crédito zerado. O sistema **não** tem fallback para outro provedor neste caso — o serviço para de responder até adicionar crédito.

---

## 17. Como Criar um Ambiente de Teste

### Opção recomendada: instância separada

1. **WhatsApp de teste:** criar nova instância no UAZAPI com número diferente
2. **Banco de dados:** apontar para banco de homologação do Protheus (ou banco de desenvolvimento)
3. **Redis:** usar `REDIS_DB=1` (ou outro número diferente do de produção)
4. **Supabase:** criar projeto separado no Supabase, ou usar schema diferente
5. **OpenAI:** mesma chave ou chave separada

**`.env` do ambiente de teste:**
```env
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Mesmo SQL Server, banco diferente
SQL_SERVER_DATABASE=ProtheusHML

# Mesmo Redis, banco diferente
REDIS_DB=1

# Nova instância UAZAPI
EVOLUTION_INSTANCE_NAME=ComexIM_Teste
```

**Subir na porta diferente:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

**Configurar webhook no UAZAPI de teste** para apontar para `http://seu_servidor:8001/webhook`.

---

## 18. Logs e Monitoramento

### Onde olhar quando algo dá errado

**1. Ver o erro mais recente:**
```bash
journalctl -u agente-comexim -n 50 --no-pager | grep -i error
```

**2. Acompanhar em tempo real:**
```bash
journalctl -u agente-comexim -f
```

**3. Ver logs de uma mensagem específica** (lembrar que o servidor está em UTC, horário de Brasília = UTC-3):
```bash
# Se a mensagem chegou às 14:30 de Brasília = 17:30 UTC
journalctl -u agente-comexim --since "2026-05-29 17:25" --until "2026-05-29 17:35" --no-pager
```

### Erros comuns e o que significam

| Erro no log | Causa | Solução |
|---|---|---|
| `insufficient_quota` | Crédito OpenAI zerado | Adicionar crédito em platform.openai.com/billing |
| `Rate limit reached... TPM` | Muitas requisições simultâneas com contexto grande | O sistema faz retry automático após 10s |
| `violates check constraint` | Valor inválido no Supabase | Verificar os valores aceitos pelo constraint |
| `No module named 'xxx'` | Pacote não instalado | `pip install xxx` no venv do servidor |
| `'Settings' object has no attribute 'xxx'` | Variável faltando no `config.py` | Adicionar o campo em `app/core/config.py` |
| `ODBC Driver not found` | Driver SQL Server não instalado | Instalar `msodbcsql17` no servidor |
| `Conexão Redis perdida` | Timeout de conexão | Normal — reconecta automaticamente |

---

*Manual gerado com base no código em produção — versão main, commit 52c8718*
