# 📦 Guia de Instalação - Agente Comexim IA

## ⚙️ Requisitos

- **Python**: 3.11 ou superior
- **Redis**: Local ou cloud (Upstash, Redis Cloud)
- **SQL Server**: Acesso ao banco Protheus
- **ODBC Driver**: ODBC Driver 17 for SQL Server

## 🔧 Instalação do ODBC Driver (Windows)

### Opção 1: Download Direto
1. Baixe: https://go.microsoft.com/fwlink/?linkid=2249004
2. Execute o instalador
3. Siga as instruções

### Opção 2: Via winget
```bash
winget install Microsoft.ODBCDriver.17
```

### Verificar instalação
```bash
odbcad32
```
Deve aparecer "ODBC Driver 17 for SQL Server" na lista.

## 🐳 Redis com Docker (Recomendado para Dev)

```bash
docker run -d --name redis-comexim -p 6379:6379 redis:alpine
```

## 📝 Passo a Passo

### 1. Clone/Download do Projeto
```bash
cd c:\Users\pedro\Desktop\agente-comexim
```

### 2. Execute o Setup Automático
```bash
setup.bat
```

Ou manual:

```bash
# Criar venv
python -m venv venv

# Ativar
venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

### 3. Configure `.env`

Copie `.env.example` para `.env`:

```bash
copy .env.example .env
```

**Configurações obrigatórias:**

```env
# Banco de dados (IMPORTANTE)
SQL_SERVER_DATABASE=NOME_DO_DATABASE_AQUI

# LLM (escolha um)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...

# ou

LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Teste a Instalação

```bash
python -c "from app.core.config import settings; print('Config OK!')"
```

### 5. Teste Conexão SQL Server

```bash
python -c "from app.core.database import sql_client; print('SQL:', sql_client.test_connection())"
```

### 6. Execute o Sistema

**Opção 1: Script automático**
```bash
run.bat
```

**Opção 2: Manual**
```bash
venv\Scripts\activate
python main.py
```

**Opção 3: Desenvolvimento (auto-reload)**
```bash
uvicorn main:app --reload --port 8000
```

## 🌐 Verificar se está Funcionando

Abra no navegador:
```
http://localhost:8000
```

Deve retornar:
```json
{
  "service": "Agente Comexim IA",
  "version": "1.0.0",
  "status": "running"
}
```

Health check:
```
http://localhost:8000/health
```

## 🐛 Troubleshooting

### Erro: "ODBC Driver not found"

**Solução**: Instale ODBC Driver 17 for SQL Server (veja acima)

### Erro: "Connection refused" (Redis)

**Solução 1**: Instale Redis localmente
```bash
# Docker
docker run -d --name redis-comexim -p 6379:6379 redis:alpine

# WSL
sudo apt install redis-server
sudo service redis-server start
```

**Solução 2**: Use Redis cloud (Upstash, Redis Cloud) e ajuste `.env`

### Erro: "Access denied" (SQL Server)

Verifique:
- Usuário: `iaSelect`
- Senha: `User_CMX#6776_Sql@`
- Host/Porta: `200.221.173.187:6776`
- Firewall liberado

### Erro: "Module not found"

```bash
pip install -r requirements.txt --upgrade
```

### Erro: LangChain/LangGraph

```bash
pip install langchain langchain-openai langchain-anthropic langgraph --upgrade
```

## 📊 Logs

Logs aparecem em:
- Console (stdout)
- Arquivo: `agente-comexim.log`

Nível de log configurável em `.env`:
```env
LOG_LEVEL=INFO  # ou DEBUG, WARNING, ERROR
```

## 🔐 Segurança

**NUNCA** commite o arquivo `.env` no Git!

Está protegido em `.gitignore`, mas verifique:
```bash
git status
```

Se `.env` aparecer, adicione ao `.gitignore`:
```
.env
```

## 🚀 Deploy (Produção)

### Variáveis de Ambiente Essenciais

```env
ENV=production
DEBUG=false
LOG_LEVEL=WARNING

# Desabilitar docs em produção
# (FastAPI já faz isso automaticamente com debug=false)
```

### Executar com Gunicorn

```bash
pip install gunicorn

gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Executar como Serviço (Windows)

Use NSSM (Non-Sucking Service Manager):
```bash
nssm install AgenteComexim "C:\Users\pedro\Desktop\agente-comexim\venv\Scripts\python.exe" "C:\Users\pedro\Desktop\agente-comexim\main.py"
nssm start AgenteComexim
```

## ✅ Checklist Final

- [ ] Python 3.11+ instalado
- [ ] ODBC Driver 17 instalado
- [ ] Redis rodando (local ou cloud)
- [ ] Arquivo `.env` configurado
- [ ] SQL Server acessível
- [ ] API Key do LLM (OpenAI ou Anthropic)
- [ ] Evolution API token configurado
- [ ] Teste de conexão SQL Server OK
- [ ] Sistema rodando em `http://localhost:8000`
- [ ] Webhook configurado na Evolution API
