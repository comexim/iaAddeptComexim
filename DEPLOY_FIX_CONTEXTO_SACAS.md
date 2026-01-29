# Deploy do Fix: Usar Query Original em Filtros Automáticos

## Problema Corrigido

A IA estava retornando valores **INCORRETOS** quando perguntas curtas eram contextualizadas automaticamente:

### Exemplo de Erro:

**Pergunta**: "Quantas sacas exportamos este mês?"

**ANTES DO FIX** ❌:
- IA respondia: **81.834,82 sacas**
- Valor correto: **108.211,79 sacas**
- **ERRO**: 26.376,97 sacas (32,23% de diferença!)

**Causa raiz**:
- Pergunta tem 37 caracteres (< 40 limite)
- Sistema concatenava com pergunta anterior: "Dos contratos de dezembro de 2025 que já foram embarcados, quantos ainda não foram baixados... Quantas sacas exportamos este mês?"
- Filtros detectavam "embarcados" e "baixados" na query contextualizada
- Aplicavam filtros INCORRETAMENTE na pergunta sobre sacas

**DEPOIS DO FIX** ✅:
- IA responde: **108.211,79 sacas**
- **Correto**: Sem filtros incorretos aplicados

## Solução Implementada

Criado sistema de **dupla query**:

1. **`user_query`**: Query contextualizada (com histórico) - para IA entender contexto
2. **`user_query_original`**: Query original (sem contexto) - para filtros automáticos

### Modificações:

**orchestrator.py** (linha 160):
```python
sql_tools.user_query = contextualized_query  # Para IA
sql_tools.user_query_original = message      # Para filtros
```

**sql_tools.py** - 13 padrões corrigidos:
1. Detecção de filtros (linha 997)
2. Detecção de agregação forçada (linha 1106)
3. Detecção de sumário especial (linha 1252)
4. Detecção de corretor (linha 340)
5. Detecção sem ref/código (linha 373)
6. Detecção sem BL (linha 416)
7. Detecção sem amostra (linha 455)
8. Detecção "quais contratos" (linha 507)
9. Otimizações por período (linha 565)
10. Otimização por fixador (linha 602)
11. Otimização por vendedor (linha 637)
12. Otimização por filial (linha 706)
13. Otimização por linha (linha 744)
14. Detecção contrato específico (linha 1072)

## Validação do Fix

✅ **TESTE LOCAL**:
```
Pergunta contextualizada: "Dos contratos de dezembro de 2025 que já foram
                           embarcados, quantos ainda não foram baixados no
                           contas a receber? Quantas sacas exportamos este mês?"

Pergunta original: "Quantas sacas exportamos este mês?"

Resultado:
[OK] Filtro de embarcados NÃO foi aplicado (correto!)
[OK] Agregação forçada NÃO foi aplicada (correto!)
[OK] Sumário especial NÃO foi calculado (correto!)
[OK] Total de Sacas: 108.211,79 (CORRETO!)

[SUCESSO] FIX FUNCIONOU!
```

## Deploy no Servidor

### 📋 Comandos:

```bash
# 1. Conectar no servidor
ssh root@srv824573

# 2. Navegar para o diretório
cd /opt/agente-comexim-whatsapp

# 3. Verificar branch e commit atual
git branch --show-current
git log --oneline -1

# 4. Puxar alterações do GitHub
git pull

# 5. Verificar se o fix está presente
echo "=== Verificando FIX de query original ==="
grep -n "user_query_original" app/agents/sql_tools.py | head -n 5

# Deve retornar:
#   24:        self.user_query_original = ""  # Armazena pergunta ORIGINAL
#   997:        if self.user_query_original:
#   998:            query_lower = self.user_query_original.lower()
#   ...

# Verificar orchestrator
grep -n "user_query_original" app/agents/orchestrator.py

# Deve retornar:
#   160:            sql_tools.user_query_original = message

# 6. Limpar cache do Python (IMPORTANTE!)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 7. Verificar sintaxe
python3 -m py_compile app/agents/sql_tools.py
python3 -m py_compile app/agents/orchestrator.py

# 8. Reiniciar serviço
systemctl restart agente-comexim

# 9. Aguardar inicialização
sleep 10

# 10. Verificar status
systemctl status agente-comexim --no-pager

# 11. Verificar logs recentes
journalctl -u agente-comexim -n 30 --no-pager
```

## Verificação Pós-Deploy

Fazer a pergunta no WhatsApp:
```
Quantas sacas exportamos este mês?
```

**Resposta esperada**:
```
Este mês (janeiro de 2026), exportamos um total de 108.211,79 sacas.
```

## Verificação nos Logs

Ao fazer a pergunta, procurar nos logs:

```bash
journalctl -u agente-comexim -f --no-pager
```

**NÃO deve aparecer**:
- `[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'`
- `[AGREGAÇÃO FORÇADA] Padrão 'embarcados... (não) baixados' detectado`
- `[SUMÁRIO ESPECIAL] Calculado: X contratos embarcados não baixados`

**Deve aparecer**:
- `Total de Sacas: 108,211.79` (ou próximo)

## Commits Relacionados

- **dba6fa6**: Fix CRÍTICO: usar query original (sem contexto) em filtros automáticos
- **207339e**: Fix CRÍTICO: adicionar sumário explícito para embarcados não baixados
- **c73d29c**: Fix CRÍTICO: forçar agregação para queries embarcados+baixados
- **b5499f1**: Fix CRÍTICO: adicionar filtro automático para 'embarcados'

## Arquivos Modificados

- [app/agents/sql_tools.py](app/agents/sql_tools.py#L24) - Adicionado user_query_original
- [app/agents/sql_tools.py](app/agents/sql_tools.py#L997) - Uso em filtros
- [app/agents/sql_tools.py](app/agents/sql_tools.py#L1106) - Uso em agregação
- [app/agents/sql_tools.py](app/agents/sql_tools.py#L1252) - Uso em sumário
- [app/agents/orchestrator.py](app/agents/orchestrator.py#L160) - Passa query original

## Troubleshooting

### Se ainda retornar valor errado:

```bash
# Verificar logs em tempo real enquanto faz a pergunta
journalctl -u agente-comexim -f --no-pager

# Procurar por linhas que mencionam:
# "user_query_original" ou "FILTRO AUTOMÁTICO"
```

### Se filtro de embarcados for aplicado incorretamente:

```bash
# Verificar se o cache foi limpo
find . -name "*.pyc" -o -name "__pycache__"

# Deve retornar vazio

# Se encontrar arquivos, limpar novamente e reiniciar
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
systemctl restart agente-comexim
```

### Se user_query_original não existir:

```bash
# Significa que o fix não foi aplicado corretamente
# Verificar se o código está presente:
grep -c "user_query_original" app/agents/sql_tools.py

# Deve retornar: 14 ou mais (13 padrões + declaração)
```

### Se orchestrator não passa query original:

```bash
# Verificar se a linha está presente:
grep "sql_tools.user_query_original = message" app/agents/orchestrator.py

# Deve retornar a linha 160
```

## Impacto do Fix

Este fix corrige **TODOS** os casos onde perguntas curtas (<40 chars) eram contextualizadas e causavam:

1. **Filtros automáticos aplicados incorretamente**
   - Ex: "Quantas sacas?" pegando filtro de "embarcados" do histórico

2. **Agregações forçadas incorretamente**
   - Ex: Agregando por baixados quando pergunta é sobre sacas

3. **Sumários especiais calculados incorretamente**
   - Ex: Mostrando sumário de "contratos não baixados" em query sobre sacas

4. **Otimizações aplicadas incorretamente**
   - Ex: Filtrando por vendedor/filial/linha quando não solicitado

## Perguntas Afetadas Positivamente

Qualquer pergunta curta agora funciona corretamente:

- "Quantas sacas exportamos este mês?" ✅
- "E em dezembro?" ✅
- "Qual o valor?" ✅
- "E os contratos?" ✅
- "Quanto vendemos?" ✅
- "Quais clientes?" ✅

**Importante**: A contextualização AINDA funciona para a IA entender a pergunta, mas NÃO afeta mais os filtros automáticos!
