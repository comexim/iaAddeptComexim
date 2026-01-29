# PROBLEMA IDENTIFICADO: Inversão de Lógica em Query sobre Contratos Não Embarcados sem BL

## Data da Descoberta
2026-01-29

## Pergunta do Usuário
```
Quantos contratos não foram embarcados e não têm BL?
Período: janeiro de 2026
```

## Resposta da IA (INCORRETA)
```
Em janeiro de 2026, há 7 contratos que foram embarcados,
mas não possuem BL. Aqui estão os 5 primeiros contratos:
1. 036/25 (BIJDENDIJK)
2. 589/25 (ATLANTIC USA IN)
3. 011/26 (INTERAMERICAN COFFE)
4. 012/26 (INTERAMERICAN COFFE)
5. 589/25 (ATLANTIC USA IN)
```

## Análise dos Dados Reais

### Classificação de Contratos em Janeiro 2026:

| Categoria | Quantidade | Sacas | Status |
|-----------|------------|-------|---------|
| **NÃO embarcados sem BL** | **15** | 13.046,37 | ✅ RESPOSTA CORRETA |
| NÃO embarcados COM BL | 23 | - | |
| EMBARCADOS sem BL | 19 | 20.335,22 | ❌ Categoria que a IA respondeu |
| EMBARCADOS com BL | 46 | - | |
| **TOTAL** | **103** | - | |

### Contratos NÃO Embarcados sem BL (15 contratos - RESPOSTA CORRETA):
1. 001/26 - NEUMANN GRUPPE USA I - 1,357.54 sacas
2. 001/26 - BERNHARD ROTHFOS GMB - 731.69 sacas
3. 034/25 - AHOLD COFFEE - 700.00 sacas
4. 036/25 - BIJDENDIJK - 324.23 sacas
5. 080/25B - F&J COMERCIO DE CAFE - 508.47 sacas
6. 080/25F - F&J COMERCIO DE CAFE - 254.23 sacas
7. 081/25B - COFFEA IMPORTACAO, E - 864.40 sacas
8. 082/25A - COFFEA IMPORTACAO, E - 762.71 sacas
9. 082/25B - COFFEA IMPORTACAO, E - 1,677.96 sacas
10. 086/25B - J R COMERCIO E EXPOR - 369.15 sacas
11. 086/25C - J R COMERCIO E EXPOR - 369.15 sacas
12. 086/25D - J R COMERCIO E EXPOR - 369.15 sacas
13. 087/25 - FINLAY BEVERAGES - 1,146.20 sacas
14. 589/25 - ATLANTIC USA IN - 2,290.67 sacas
15. 592/25 - FINLAY BEVERAGES - 1,320.90 sacas

### Contratos EMBARCADOS sem BL (19 contratos - categoria ERRADA):
1. 003/26 - VOLCAFE - Saída: 20260203
2. 011/26 - INTERAMERICAN COFFE - Saída: 20260129
3. 012/26 - INTERAMERICAN COFFE - Saída: 20260203
4. 019/26 - LOS CINCO HISPANOS S - Saída: 20260130
5. 021/26 - LOS CINCO HISPANOS S - Saída: 20260130
6. 256/25R - JDE - Saída: 20260203
7. 256/25S - JDE - Saída: 20260202
8. 400/25A - BERNHARD ROTHFOS GMB - Saída: 20260203
9. 477/25 - UCC-COFFEE SERVICES - Saída: 20260129
10. 483/25 - COMEXIM EUROPE GMBH. - Saída: 20260203
... (mais 9 contratos)

## Erros Identificados

### ❌ Erro 1: INVERSÃO DE LÓGICA
- **Perguntado**: Contratos que **NÃO foram embarcados** e não têm BL
- **Respondido**: Contratos que **FORAM embarcados** mas não têm BL
- **Impacto**: A IA respondeu sobre a categoria OPOSTA

### ❌ Erro 2: NÚMERO INCORRETO
- **IA disse**: 7 contratos
- **Realidade**:
  - 15 contratos NÃO embarcados sem BL (correto)
  - 19 contratos EMBARCADOS sem BL (categoria errada)
- **Nenhuma categoria tem 7 contratos!**

### ❌ Erro 3: CONTRATOS LISTADOS INCORRETOS
- A IA listou:
  1. 036/25 (BIJDENDIJK) - ✅ ESTÁ na lista de NÃO embarcados
  2. 589/25 (ATLANTIC USA IN) - ✅ ESTÁ na lista de NÃO embarcados
  3. 011/26 (INTERAMERICAN COFFE) - ❌ ESTÁ na lista de EMBARCADOS
  4. 012/26 (INTERAMERICAN COFFE) - ❌ ESTÁ na lista de EMBARCADOS
  5. 589/25 (ATLANTIC USA IN) - ✅ Repetido

- **2 contratos estão EMBARCADOS** (011/26 e 012/26 têm saidaNavio)
- **2 contratos estão NÃO EMBARCADOS** (036/25 e 589/25)
- **Mix incorreto de ambas as categorias!**

## Possíveis Causas

### 1. Problema no Processamento da Negação
- Query: "Quantos contratos **não foram embarcados**"
- A IA pode estar:
  - Ignorando a negação "não"
  - Invertendo a lógica da negação
  - Confundindo com histórico de conversas

### 2. Problema no Filtro Automático
- Verificar se filtro de "sem BL" está funcionando
- Verificar se filtro de "não embarcados" está sendo aplicado

### 3. Problema na Agregação/Contagem
- Tool retornou dados corretos?
- IA interpretou corretamente o resultado?

### 4. Problema de Contexto
- Similar ao problema anterior de "sacas" que foi resolvido
- Query pode estar pegando contexto de perguntas anteriores

## Resposta Correta

```
Em janeiro de 2026, há 15 contratos que NÃO foram embarcados e não têm BL.
Aqui estão os 5 primeiros contratos e seus respectivos clientes:

1. 001/26 (NEUMANN GRUPPE USA I)
2. 001/26 (BERNHARD ROTHFOS GMB)
3. 034/25 (AHOLD COFFEE)
4. 036/25 (BIJDENDIJK)
5. 080/25B (F&J COMERCIO DE CAFE)
```

## Próximos Passos

1. ✅ Validar dados no banco de dados (CONCLUÍDO)
2. 🔍 Verificar logs do servidor para ver:
   - Que dados a tool retornou
   - Como a IA interpretou esses dados
   - Se houve algum filtro aplicado incorretamente
3. 🔧 Implementar fix baseado na causa raiz identificada
4. ✅ Validar fix localmente
5. 🚀 Deploy para servidor
6. ✅ Teste final no WhatsApp

## Arquivos Relacionados

- `test_nao_embarcados_sem_bl_detalhado.py` - Script de validação
- `resultado_detalhado_nao_embarcados_bl.txt` - Resultado detalhado
- `app/agents/sql_tools.py` - Lógica de filtros
- `app/agents/orchestrator.py` - Processamento de queries

## Status

🔴 **PROBLEMA CONFIRMADO - AGUARDANDO ANÁLISE DE LOGS**
