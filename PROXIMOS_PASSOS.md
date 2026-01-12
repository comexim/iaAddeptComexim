# Próximos Passos - Implementação Final

## Status Atual

✅ Sistema de aprendizado adaptativo **100% implementado**

### Módulos Implementados

1. ✅ Modelos de dados ([app/models/preferences.py](app/models/preferences.py))
2. ✅ Cliente Supabase ([app/core/supabase_client.py](app/core/supabase_client.py))
3. ✅ Sistema de detecção de feedback ([app/services/preference_learning.py](app/services/preference_learning.py))
4. ✅ Integração no orquestrador ([app/agents/orchestrator.py](app/agents/orchestrator.py))
5. ✅ Documentação completa ([docs/SISTEMA_APRENDIZADO.md](docs/SISTEMA_APRENDIZADO.md))

## Passo 1: Configurar Banco de Dados Supabase

### 1.1 Acesse o Dashboard do Supabase

URL: https://dotybczrhvsyhcchxugu.supabase.co

### 1.2 Execute o Script SQL

1. Vá em: **SQL Editor** → **New Query**
2. Copie todo o conteúdo de: [docs/supabase_setup.sql](docs/supabase_setup.sql)
3. Execute (Run)

Isso criará:
- Tabela `user_preferences`
- Tabela `preference_learning_log`
- Triggers automáticos
- 5 usuários pré-populados

### 1.3 Verifique a Instalação

Execute no SQL Editor:

```sql
SELECT * FROM user_preferences;
SELECT * FROM preference_learning_log;
```

Deve retornar 5 usuários com preferências padrão.

## Passo 2: Testar Sistema de Aprendizado

### 2.1 Teste de Conexão Supabase

```bash
python -c "from app.core.supabase_client import supabase_client; import asyncio; asyncio.run(supabase_client.get_user_preferences('5511994825640'))"
```

Deve retornar preferências do usuário Pedro Miranda.

### 2.2 Teste de Detecção de Feedback

Crie arquivo: `test_preference_learning.py`

```python
import asyncio
from app.services.preference_learning import preference_learning

async def test_detection():
    # Teste 1: Detecção de mensagem curta
    feedbacks = await preference_learning.detect_feedback(
        user_message="diminua a mensagem, está muito longa",
        telefone="5511994825640"
    )

    print("=== TESTE 1: Diminuir mensagem ===")
    for fb in feedbacks:
        print(f"Tipo: {fb.tipo}")
        print(f"Valor: {fb.valor}")
        print(f"Confiança: {fb.confianca:.0%}")
        print(f"Aplicar: {fb.deve_aplicar}")
        print()

    # Teste 2: Detecção de tom casual
    feedbacks = await preference_learning.detect_feedback(
        user_message="seja mais informal, pode relaxar",
        telefone="5511994825640"
    )

    print("=== TESTE 2: Tom casual ===")
    for fb in feedbacks:
        print(f"Tipo: {fb.tipo}")
        print(f"Valor: {fb.valor}")
        print(f"Confiança: {fb.confianca:.0%}")
        print()

asyncio.run(test_detection())
```

Execute:
```bash
python test_preference_learning.py
```

## Passo 3: Testar Integração Completa

### 3.1 Execute o Sistema

```bash
python main.py
```

### 3.2 Teste via WhatsApp

**Fluxo de teste:**

1. Envie mensagem: "Quanto temos em estoque?"
   - Sistema responde normalmente

2. Envie feedback: "diminua a mensagem"
   - Sistema detecta: nivel_detalhe → resumido
   - Responde confirmando: _[Preferência atualizada: nivel_detalhe → resumido]_

3. Envie nova pergunta: "E as vendas de dezembro?"
   - Resposta agora será MUITO mais curta (máx 3 linhas)

4. Teste outros feedbacks:
   - "seja mais casual" → tom_de_voz = casual
   - "use tópicos" → formato_resposta = bullet_points
   - "sem emoji" → emojis_habilitados = false

### 3.3 Verifique Logs

```bash
# No console devem aparecer:
[INFO] Preferências carregadas: Tom: profissional, Detalhamento: medio...
[APRENDIZADO] 5511994825640: nivel_detalhe = resumido (confiança: 90%)
[INFO] Preferências atualizadas, recriando agente...
```

### 3.4 Verifique Banco de Dados

No Supabase SQL Editor:

```sql
-- Ver preferências atualizadas
SELECT
    telefone,
    nome,
    nivel_detalhe,
    tom_de_voz,
    formato_resposta,
    emojis_habilitados,
    feedback_count,
    confidence_score,
    learning_history
FROM user_preferences
WHERE telefone = '5511994825640';

-- Ver histórico de aprendizado
SELECT
    telefone,
    feedback_type,
    detected_pattern,
    confidence_score,
    applied,
    details,
    created_at
FROM preference_learning_log
WHERE telefone = '5511994825640'
ORDER BY created_at DESC;
```

## Passo 4: Ajustes Finais (Opcional)

### 4.1 Ajustar Threshold de Confiança

Se sistema está aplicando muito/pouco feedback, ajuste em [app/services/preference_learning.py:121](app/services/preference_learning.py#L121):

```python
deve_aplicar=confianca >= 0.8,  # Altere 0.8 para 0.7 (mais sensível) ou 0.9 (menos)
```

### 4.2 Adicionar Novos Padrões de Feedback

Edite `FEEDBACK_PATTERNS` em [app/services/preference_learning.py:20](app/services/preference_learning.py#L20):

```python
FEEDBACK_PATTERNS = {
    "nivel_detalhe": [
        # Adicione seus padrões aqui
        (r"novo padrão regex", "resumido", 0.9),
    ],
}
```

### 4.3 Desativar Sistema de Aprendizado

No `.env`:

```env
ENABLE_PREFERENCE_LEARNING=false
```

## Passo 5: Deploy em Produção

### 5.1 Checklist de Produção

- [ ] Supabase em produção configurado
- [ ] Credenciais em variáveis de ambiente (não em .env commitado)
- [ ] Row Level Security (RLS) ativado no Supabase
- [ ] Logs configurados (LOG_LEVEL=WARNING)
- [ ] Monitoramento de erros configurado

### 5.2 Variáveis de Ambiente Produção

```env
ENV=production
DEBUG=false
LOG_LEVEL=WARNING

SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

ENABLE_PREFERENCE_LEARNING=true
```

### 5.3 Row Level Security (RLS)

No Supabase, ative RLS para `user_preferences`:

```sql
-- Habilitar RLS
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- Política: Usuários só veem suas próprias preferências
CREATE POLICY "Usuários veem apenas suas preferências"
ON user_preferences
FOR ALL
USING (telefone = current_setting('app.current_user_phone', true));
```

## Estrutura de Arquivos Criada

```
agente-comexim/
├── app/
│   ├── core/
│   │   ├── supabase_client.py       ✅ NOVO
│   ├── models/
│   │   ├── preferences.py           ✅ NOVO
│   ├── services/
│   │   ├── preference_learning.py   ✅ NOVO
│   ├── agents/
│   │   ├── orchestrator.py          ✅ ATUALIZADO
├── docs/
│   ├── supabase_setup.sql           ✅ NOVO
│   ├── SISTEMA_APRENDIZADO.md       ✅ NOVO
├── .env                             ✅ ATUALIZADO
├── requirements.txt                 ✅ ATUALIZADO
└── PROXIMOS_PASSOS.md              ✅ ESTE ARQUIVO
```

## Troubleshooting

### Erro: "supabase module not found"

```bash
python -m pip install supabase --upgrade
```

### Erro: "table user_preferences does not exist"

Execute o script SQL: [docs/supabase_setup.sql](docs/supabase_setup.sql)

### Feedback não está sendo detectado

1. Verifique `ENABLE_PREFERENCE_LEARNING=true` no `.env`
2. Aumente logging: `LOG_LEVEL=DEBUG`
3. Teste detecção manualmente com script do Passo 2.2

### Agente não está usando preferências

1. Verifique logs: deve aparecer "Preferências carregadas"
2. Confirme que usuário existe no Supabase
3. Teste: `python -c "from app.core.supabase_client import supabase_client; import asyncio; print(asyncio.run(supabase_client.get_user_preferences('SEU_TELEFONE')))"`

## Conclusão

O sistema está **pronto para uso**!

Próximos passos:
1. Execute script SQL no Supabase
2. Teste detecção de feedback
3. Teste via WhatsApp
4. Monitor logs e banco de dados

Para dúvidas, consulte: [docs/SISTEMA_APRENDIZADO.md](docs/SISTEMA_APRENDIZADO.md)
