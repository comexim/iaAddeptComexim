# 🔄 Criação de Contratos via API ADA

Esta funcionalidade permite criar contratos de venda/exportação diretamente através da conversa com a IA.

---

## 📋 Como Funciona

### 1. **Usuário faz pedido em linguagem natural**
```
"Quero criar um contrato de venda para Nestlé, 
60.000 kg de café premium, FOB, embarque em maio/2026"
```

### 2. **IA extrai os dados automaticamente**
- Cliente: Nestlé
- Quantidade: 60.000 kg  
- Padrão: Premium
- Condição: FOB
- Mês de embarque: maio/2026

### 3. **IA verifica campos obrigatórios**
Se faltar algo, a IA pergunta:
```
"Para criar o contrato, preciso dos seguintes dados:
- Modalidade de pagamento
- Moeda de fixação
- Tipo de contrato"
```

### 4. **Usuário completa os dados**
```
"Modalidade é à vista, moeda USD, tipo exportação"
```

### 5. **IA cria o contrato via API**
```
✅ Contrato criado com sucesso!
Número: 123/26
Cliente: NESTLE
Quantidade: 60.000 kg
```

---

## 🎯 Campos do Contrato

### Campos Obrigatórios:

#### **Cliente** (um dos dois):
- **Opção 1**: `codigoCliente` + `lojaCliente`  
- **Opção 2**: `nomeCliente`

#### **Condicional**:
- `dataPrevisaoEntrega` - **obrigatório** apenas se `condicaoEntrega` == 'ENT'

### Campos Opcionais:

**Detalhes do Contrato:**
- `codigoEmbalagem` - Código da embalagem
- `quantidadeKg` - Quantidade em KG
- `padraoQualidade` - Padrão de qualidade
- `modalidadePagamento` - Modalidade de pagamento
- `quantidadeContainer` - Quantidade de containers
- `mesEmbarque` - Mês de embarque (ex: "maio/2026")
- `exigeEudr` - Exige EUDR? (true/false)
- `amostraPreEmbarque` - Amostra pré-embarque? (true/false)
- `condicaoEntrega` - FOB, ENT, etc.
- `moedaFixacao` - Moeda (USD, BRL, etc.)
- `tipoContrato` - Tipo de contrato
- `condicaoPeso` - Condição de peso

**Arrays:**
- `fixacaoContrato` - Lista de fixações
- `comissaoContrato` - Lista de comissões

---

## 💬 Exemplos de Conversas

### **Exemplo 1: Contrato Completo**

```
👤 Usuário:
"Quero criar um contrato de venda para Nestlé Araras,
quantidade 60.000 kg, padrão Premium, modalidade à vista,
2 containers, embarque em maio/2026, condição FOB,
moeda USD, tipo exportação"

🤖 IA:
✅ Contrato criado com sucesso!

Detalhes:
- Número: 123/26
- Cliente: NESTLE ARARAS
- Quantidade: 60.000 kg
- Condição: FOB
- Embarque: maio/2026
```

---

### **Exemplo 2: IA Pergunta Dados Faltantes**

```
👤 Usuário:
"Criar um contrato para Starbucks"

🤖 IA:
"Para criar o contrato, preciso dos seguintes dados:
- Quantidade em KG
- Modalidade de pagamento
- Condição de entrega
- Moeda de fixação"

👤 Usuário:
"45.000 kg, à vista, FOB, USD"

🤖 IA:
✅ Contrato criado com sucesso!
...
```

---

### **Exemplo 3: Condição de Entrega ENT**

```
👤 Usuário:
"Contrato UCC, 30.000 kg, condição ENT, entrega em 15/06/2026"

🤖 IA:
✅ Contrato criado com sucesso!
...
```

---

## 🧪 Como Testar

### **1. Testar apenas a API**

```bash
python test_ada_api.py
```

Isso testa:
- ✅ Autenticação (obter token)
- ✅ Conexão com API

---

### **2. Testar via IA (sem WhatsApp)**

```bash
python test_criar_contrato_ada.py
```

Isso testa:
- ✅ IA extraindo dados da conversa
- ✅ IA perguntando dados faltantes
- ✅ Criação de contrato via API

---

### **3. Testar no modo interativo**

```bash
python testar_mensagem.py
```

Depois digite:
```
Você: Quero criar um contrato para Nestlé, 60.000 kg, FOB
🤖 Agente: [resposta]
```

---

## ⚙️ Configuração

### **1. Adicione ao `.env`:**

```env
# ADA API (Criação de Contratos)
ADA_API_URL=http://200.221.173.187:8085
ADA_USERNAME=lucas.oliveira
ADA_PASSWORD=ornn@30com
```

### **2. Verifique a configuração:**

```bash
python test_ada_api.py
```

---

## 🔒 Segurança

✅ **Token OAuth2** - Renovado automaticamente  
✅ **HTTPS** - Comunicação segura  
✅ **Validação** - Campos validados antes de enviar  
✅ **Logs** - Todas as operações são logadas  

---

## 📊 Arquitetura

```
Usuário (conversa natural)
    ↓
IA (extrai dados)
    ↓
Validação (campos obrigatórios)
    ↓
[Se faltar] → IA pergunta
    ↓
[Se completo] → API ADA
    ↓
Token OAuth2
    ↓
POST /rest/ia/api/v1/postADA/vendaExp
    ↓
✅ Contrato criado!
```

---

## 🐛 Troubleshooting

### **Erro de autenticação**
```
❌ Falha na autenticação ADA API: 401
```
**Solução**: Verifique `ADA_USERNAME` e `ADA_PASSWORD` no `.env`

---

### **Erro "campos faltando"**
```
PRECISA_PERGUNTAR: Para criar o contrato, preciso dos seguintes dados...
```
**Solução**: Normal! A IA vai perguntar os dados. Responda normalmente.

---

### **Timeout na API**
```
❌ Erro ao criar contrato: timeout
```
**Solução**: Verifique conexão com a rede e `ADA_API_URL`

---

## 📚 Arquivos Criados

| Arquivo | Descrição |
|---------|-----------|
| `app/models/contrato_ada.py` | Models Pydantic do contrato |
| `app/core/ada_api_client.py` | Cliente da API ADA |
| `app/agents/ada_tools.py` | Tool LangChain para IA |
| `test_ada_api.py` | Teste de conexão API |
| `test_criar_contrato_ada.py` | Teste completo com IA |
| `CRIAR_CONTRATOS_ADA.md` | Este guia |

---

## ✅ Status

**Implementação**: Completa  
**Testes**: Prontos  
**Integração**: WhatsApp + Teste Direto  
**Documentação**: Completa  

🎉 **Pronto para uso!**
