# Sistema de Aprendizado Adaptativo de Preferências

## Visão Geral

O sistema de aprendizado adaptativo permite que a IA aprenda as preferências de comunicação de cada usuário automaticamente, sem necessidade de configuração manual.

## Como Funciona

### 1. Detecção de Feedback

A IA detecta quando o usuário expressa preferências através de duas estratégias:

#### A) Detecção via Regex (Alta Confiança, Rápida)

Padrões comuns pré-definidos:

**Nível de Detalhe:**
- "diminua a mensagem" / "reduza" / "seja mais breve" → `resumido`
- "muito grande" / "muito longa" → `resumido`
- "aumente" / "detalhe mais" / "mais completo" → `detalhado`
- "médio" / "normal" / "padrão" → `medio`

**Tom de Voz:**
- "seja mais formal" / "profissional" → `profissional`
- "seja mais casual" / "descontraído" → `casual`
- "técnico" / "metodologia" → `tecnico`
- "executivo" / "direto ao ponto" → `executivo`

**Formato de Resposta:**
- "bullet" / "tópicos" / "lista" → `bullet_points`
- "tabela" / "tabular" → `tabular`
- "narrativa" / "história" → `narrativo`
- "texto corrido" → `texto`

**Emojis:**
- "sem emoji" / "tire emoji" → `false`
- "com emoji" / "use emoji" → `true`

#### B) Detecção via LLM (Casos Ambíguos)

Quando regex não detecta ou tem baixa confiança, o sistema usa GPT-4o-mini ou Claude Haiku para:
- Analisar contexto da mensagem
- Identificar feedback implícito
- Classificar com score de confiança

### 2. Aplicação do Aprendizado

**Threshold de Confiança:** 0.8 (80%)

Apenas feedbacks com confiança >= 80% são aplicados automaticamente.

**Processo:**
1. Feedback detectado com confiança >= 0.8
2. Preferência atualizada no Supabase
3. Learning history registrado (audit trail)
4. Agente recriado com novo system prompt customizado
5. Confirmação visual enviada ao usuário

### 3. Injeção no Prompt

Quando preferências são carregadas, são injetadas no system prompt:

```
# INSTRUÇÕES PERSONALIZADAS DO USUÁRIO

Use tom casual, amigável e direto. Seja objetivo sem formalidades excessivas.

Respostas MUITO breves (máximo 3 linhas). Apenas números-chave e insights principais.

SEMPRE use bullet points (•) e tópicos para organizar informações.

Use emojis moderadamente para tornar resposta mais amigável (máximo 2-3 por mensagem).

IMPORTANTE: Siga RIGOROSAMENTE as instruções personalizadas acima ao formatar suas respostas.
```

## Estrutura de Dados

### Tabela: user_preferences

```sql
CREATE TABLE user_preferences (
    telefone TEXT PRIMARY KEY,
    nome TEXT,
    email TEXT,

    -- Preferências de Comunicação
    nivel_detalhe TEXT DEFAULT 'medio',
    tom_de_voz TEXT DEFAULT 'profissional',
    formato_resposta TEXT DEFAULT 'texto',

    -- Formatação
    formato_moeda TEXT DEFAULT 'BRL',
    formato_data TEXT DEFAULT 'DD/MM/YYYY',
    emojis_habilitados BOOLEAN DEFAULT true,

    -- Personalização
    saudacao_customizada TEXT,
    assinatura_customizada TEXT,
    areas_interesse TEXT[],
    metricas_favoritas TEXT[],
    instrucoes_adicionais TEXT,

    -- Metadata de Aprendizado
    learning_history JSONB DEFAULT '[]',
    confidence_score FLOAT DEFAULT 0.5,
    feedback_count INTEGER DEFAULT 0,
    last_feedback_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tabela: preference_learning_log

Audit trail completo de todos os feedbacks (aplicados ou não):

```sql
CREATE TABLE preference_learning_log (
    id SERIAL PRIMARY KEY,
    telefone TEXT REFERENCES user_preferences(telefone) ON DELETE CASCADE,
    feedback_type TEXT,
    detected_pattern TEXT,
    confidence_score FLOAT,
    applied BOOLEAN,
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## Exemplos de Uso

### Exemplo 1: Usuário Quer Respostas Mais Curtas

**Usuário:** "Suas respostas estão muito longas, diminua a mensagem"

**Sistema:**
1. Regex detecta: `(diminua|reduza)` → nivel_detalhe = "resumido" (confiança: 0.9)
2. Aplica mudança no Supabase
3. Recria agente com novo prompt
4. Responde: "Entendido! [dados]... _[Preferência atualizada: nivel_detalhe → resumido]_"

**Próximas respostas:** máximo 3 linhas, apenas insights principais

### Exemplo 2: Usuário Quer Tom Mais Casual

**Usuário:** "Pode ser mais informal, relaxa"

**Sistema:**
1. Regex detecta: `pode (relaxar|ser informal)` → tom_de_voz = "casual" (confiança: 0.85)
2. Aplica mudança
3. Responde com tom descontraído

**Próximas respostas:** linguagem casual, menos formalidades

### Exemplo 3: Usuário Quer Bullet Points

**Usuário:** "Organiza em tópicos pra ficar mais fácil de ler"

**Sistema:**
1. Regex detecta: `organiza em (itens|lista)` → formato_resposta = "bullet_points" (confiança: 0.85)
2. Aplica mudança
3. Todas as próximas respostas usam bullet points

### Exemplo 4: Feedback Ambíguo (Via LLM)

**Usuário:** "Gostaria de algo mais direto e objetivo"

**Sistema:**
1. Regex não detecta (baixa confiança)
2. LLM analisa e detecta: tom_de_voz = "executivo" (confiança: 0.9)
3. Aplica mudança

**Próximas respostas:** extremamente concisas, focadas em insights estratégicos

## Configuração

### .env

```env
# Ativar/desativar sistema de aprendizado
ENABLE_PREFERENCE_LEARNING=true

# Supabase (obrigatório)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

### Inicialização do Banco

Execute o script SQL no Supabase:

```bash
# 1. Acesse Supabase Dashboard
# 2. SQL Editor
# 3. Cole conteúdo de docs/supabase_setup.sql
# 4. Execute
```

## Arquitetura

```
Usuário: "diminua a mensagem"
    ↓
[WhatsApp] → Evolution API
    ↓
[FastAPI Webhook] → app/api/webhook.py
    ↓
[OrquestradorAgente] → app/agents/orchestrator.py
    ↓
[PreferenceLearningSystem] → app/services/preference_learning.py
    ├── detect_feedback() → Regex + LLM
    ├── apply_feedback() → Supabase update
    └── log_feedback() → Audit trail
    ↓
[Supabase] user_preferences + learning_log
    ↓
[Agente Recriado] com novo system prompt customizado
    ↓
[Resposta Personalizada] + confirmação visual
```

## Métricas de Aprendizado

Cada preferência armazena:

- **confidence_score**: 0.0 a 1.0 (quanto maior, mais confiante)
- **feedback_count**: número total de ajustes feitos
- **last_feedback_at**: timestamp do último aprendizado
- **learning_history**: array JSONB com histórico completo

### Visualizar Histórico

```sql
SELECT
    telefone,
    nome,
    nivel_detalhe,
    tom_de_voz,
    formato_resposta,
    feedback_count,
    confidence_score,
    learning_history
FROM user_preferences
WHERE telefone = '5511999999999';
```

## Debugging

### Verificar Detecção de Feedback

```python
from app.services.preference_learning import preference_learning

feedbacks = await preference_learning.detect_feedback(
    user_message="diminua a mensagem",
    telefone="5511999999999"
)

for fb in feedbacks:
    print(f"{fb.tipo} → {fb.valor} (confiança: {fb.confianca:.0%})")
```

### Verificar Preferências Carregadas

```python
from app.core.supabase_client import supabase_client

prefs = await supabase_client.get_user_preferences("5511999999999")
print(prefs.get_summary())
print(prefs.get_custom_instructions())
```

## Limitações e Melhorias Futuras

### Limitações Atuais

1. Apenas português (padrões regex em PT-BR)
2. Feedback deve ser explícito (baixa taxa de detecção implícita)
3. Não detecta preferências contextuais (ex: "resumido apenas para vendas")

### Roadmap

- [ ] Suporte multi-idioma
- [ ] Detecção de preferências contextuais por módulo
- [ ] Machine learning para melhorar detecção de padrões
- [ ] Dashboard web para visualização de aprendizados
- [ ] A/B testing de respostas para otimizar preferências
- [ ] Análise de sentimento para ajustar tom automaticamente

## Segurança

- **Service Role Key**: usado apenas server-side
- **Row Level Security (RLS)**: cada usuário acessa apenas suas preferências
- **Audit Trail**: todas as mudanças registradas com timestamp
- **Rollback**: learning_history permite reverter mudanças

## Monitoramento

Logs importantes aparecem em:

```
[INFO] Preferências carregadas: Tom: profissional, Detalhamento: medio...
[APRENDIZADO] 5511999999999: nivel_detalhe = resumido (confiança: 90%)
[INFO] Preferências atualizadas, recriando agente...
```

## Suporte

Para questões ou bugs relacionados ao sistema de aprendizado:

1. Verifique logs do sistema
2. Consulte `preference_learning_log` no Supabase
3. Teste detecção com script de debug acima
