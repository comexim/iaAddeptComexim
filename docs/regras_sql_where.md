# Regras de Uso do WHERE nas Consultas SQL

## ⚠️ REGRA CRÍTICA

O banco de dados contém **anos de histórico**. Consultas sem filtros de data podem retornar **milhões de registros** e causar:
- Timeout no banco
- Mensagens gigantes no WhatsApp
- Experiência ruim do usuário

---

## 🔴 Funções que EXIGEM WHERE (Dados Volumosos)

### 1. **IA_Vendas()** - WHERE OBRIGATÓRIO
```sql
SELECT * FROM IA_Vendas() WHERE mesEmbarque = '2025/12'
```

**Filtro obrigatório**: `mesEmbarque` (formato: YYYY/MM)

**Fluxo de validação**:
```
User: "Quanto vendemos?"
AI: "Qual período você gostaria de consultar? (Ex: dezembro de 2025)"
User: "dezembro"
AI: [Executa query com WHERE mesEmbarque = '2025/12']
```

---

### 2. **IA_Compras()** - WHERE OBRIGATÓRIO
```sql
SELECT * FROM IA_Compras() WHERE emissao >= '20251205'
```

**Filtro obrigatório**: `emissao` (formato: YYYYMMDD)

**Fluxo de validação**:
```
User: "Quais foram as compras?"
AI: "A partir de qual data você gostaria de consultar? (Ex: últimos 7 dias, dezembro)"
User: "últimos 7 dias"
AI: [Calcula data_inicio e executa query com WHERE emissao >= '20251208']
```

---

### 3. **IA_ContasPagas()** - WHERE OBRIGATÓRIO
```sql
SELECT * FROM IA_ContasPagas() WHERE emissao >= '20251205'
```

**Filtro obrigatório**: `emissao` (formato: YYYYMMDD)

**Fluxo de validação**:
```
User: "Quanto pagamos?"
AI: "Qual período? (Ex: este mês, últimos 30 dias)"
User: "este mês"
AI: [Calcula primeiro dia do mês e executa query]
```

---

### 4. **IA_ContasAPagar()** - WHERE OBRIGATÓRIO
```sql
SELECT * FROM IA_ContasAPagar() WHERE vencimento = '20251212'
```

**Filtro obrigatório**: `vencimento` (formato: YYYYMMDD)

**Fluxo de validação**:
```
User: "O que temos a pagar?"
AI: "Para qual data de vencimento? (Ex: hoje, próximos 7 dias, 12/12/2025)"
User: "próximos 7 dias"
AI: [Executa query para cada dia ou range]
```

---

### 5. **IA_Orcamento()** - WHERE OBRIGATÓRIO
```sql
SELECT * FROM IA_Orcamento() WHERE ano >= '2025' AND mes = '12'
```

**Filtros obrigatórios**: `ano` (YYYY), `mes` (MM)

**Fluxo de validação**:
```
User: "Como está o orçamento?"
AI: "De qual mês e ano? (Ex: dezembro de 2025)"
User: "dezembro de 2025"
AI: [Executa query com WHERE ano = '2025' AND mes = '12']
```

---

## 🟢 Funções SEM WHERE (Snapshots/Poucos Dados)

Essas funções retornam **estado atual** ou **poucos registros**, **não exigem filtro**:

### 1. **IA_SaldoBancario()** - SEM WHERE
```sql
SELECT * FROM IA_SaldoBancario()
```
**Motivo**: Retorna apenas saldo atual de cada conta bancária (≈ 5-10 registros)

---

### 2. **IA_Estoque()** - SEM WHERE
```sql
SELECT * FROM IA_Estoque()
```
**Motivo**: Retorna snapshot atual do estoque (quantidade limitada de produtos)

---

## 🤖 Implementação no AI Agent

### Estratégia de Validação

```python
# agents/sql_validator.py

FUNCTIONS_REQUIRING_WHERE = {
    "IA_Vendas": {
        "required_field": "mesEmbarque",
        "format": "YYYY/MM",
        "prompt": "Qual período você gostaria de consultar? (Ex: dezembro de 2025, 2025/12)"
    },
    "IA_Compras": {
        "required_field": "emissao",
        "format": "YYYYMMDD",
        "prompt": "A partir de qual data? (Ex: últimos 7 dias, 05/12/2025)"
    },
    "IA_ContasPagas": {
        "required_field": "emissao",
        "format": "YYYYMMDD",
        "prompt": "Qual período de pagamento? (Ex: este mês, últimos 30 dias)"
    },
    "IA_ContasAPagar": {
        "required_field": "vencimento",
        "format": "YYYYMMDD",
        "prompt": "Para qual data de vencimento? (Ex: hoje, próximos 7 dias)"
    },
    "IA_Orcamento": {
        "required_fields": ["ano", "mes"],
        "format": "ano=YYYY, mes=MM",
        "prompt": "De qual mês e ano? (Ex: dezembro de 2025)"
    }
}

FUNCTIONS_WITHOUT_WHERE = ["IA_SaldoBancario", "IA_Estoque"]


def validate_query_has_filters(function_name: str, user_question: str, filters: dict = None) -> dict:
    """
    Valida se query possui filtros obrigatórios antes de executar.

    Returns:
        {
            "valid": bool,
            "error_message": str | None,
            "needs_clarification": bool
        }
    """

    # Funções sem WHERE podem executar direto
    if function_name in FUNCTIONS_WITHOUT_WHERE:
        return {"valid": True, "needs_clarification": False}

    # Funções com WHERE obrigatório
    if function_name in FUNCTIONS_REQUIRING_WHERE:
        config = FUNCTIONS_REQUIRING_WHERE[function_name]

        # Verifica se filtros foram fornecidos
        if not filters:
            return {
                "valid": False,
                "needs_clarification": True,
                "error_message": config["prompt"]
            }

        # Valida campos obrigatórios
        if "required_fields" in config:
            missing = [f for f in config["required_fields"] if f not in filters]
            if missing:
                return {
                    "valid": False,
                    "needs_clarification": True,
                    "error_message": config["prompt"]
                }
        elif config["required_field"] not in filters:
            return {
                "valid": False,
                "needs_clarification": True,
                "error_message": config["prompt"]
            }

        return {"valid": True, "needs_clarification": False}

    # Função desconhecida
    return {"valid": False, "error_message": "Função SQL não configurada."}
```

---

## 📝 Prompt do AI Agent (Adição)

```xml
<mandatory-rules>
...
- ANTES de executar qualquer consulta SQL, verifique se a função EXIGE filtros de data.
- Funções que EXIGEM WHERE: IA_Vendas, IA_Compras, IA_ContasPagas, IA_ContasAPagar, IA_Orcamento
- Se o usuário não informar período, PERGUNTE antes de executar a query.
- Nunca execute queries sem WHERE em funções que exigem filtro de data.
- Funções IA_SaldoBancario e IA_Estoque podem ser executadas sem filtros.
</mandatory-rules>

<date-parameter-handling>
Quando o usuário informar datas em linguagem natural:
- "hoje" → data atual (YYYYMMDD)
- "ontem" → data atual - 1 dia
- "últimos 7 dias" → data atual - 7 dias até hoje
- "este mês" → primeiro dia do mês até hoje
- "dezembro" → inferir ano atual, formato YYYY/MM
- "próximos 7 dias" → hoje até hoje + 7 dias

SEMPRE confirme o período calculado com o usuário antes de executar.
</date-parameter-handling>
```

---

## 🎯 Exemplos de Conversação

### Exemplo 1: Vendas sem período
```
User: "Quanto vendemos?"
AI: "Qual período você gostaria de consultar? (Ex: dezembro de 2025)"
User: "dezembro"
AI: [Infere 2025/12, executa query]
AI: "Em dezembro de 2025, o faturamento foi de R$ 1.245.380,00..."
```

### Exemplo 2: Compras com período
```
User: "Quais foram as compras dos últimos 7 dias?"
AI: [Calcula: hoje = 15/12/2025, 7 dias atrás = 08/12/2025]
AI: [Executa: SELECT * FROM IA_Compras() WHERE emissao >= '20251208']
AI: "Nos últimos 7 dias, foram realizadas 23 compras no valor total de..."
```

### Exemplo 3: Saldo bancário (sem WHERE)
```
User: "Qual o saldo disponível?"
AI: [Executa direto: SELECT * FROM IA_SaldoBancario()]
AI: "O saldo disponível em todas as contas é de R$ 450.320,00..."
```

---

## ✅ Checklist de Implementação

- [ ] Criar validador de filtros obrigatórios
- [ ] Adicionar regras no system prompt do AI Agent
- [ ] Implementar parser de datas em linguagem natural
- [ ] Criar testes para cada função SQL
- [ ] Adicionar logs de queries executadas (auditoria)
- [ ] Implementar timeout de 30s para queries grandes
