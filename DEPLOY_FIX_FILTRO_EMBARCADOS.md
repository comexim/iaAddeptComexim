# Deploy do Fix: Filtro Automático para "Embarcados"

## Problema Corrigido

A IA estava retornando contratos **INCORRETOS** quando a pergunta mencionava "contratos que já foram embarcados":

### Exemplo de Erro:

**Pergunta**: "Dos contratos de dezembro de 2025 que já foram embarcados, quantos ainda não foram baixados no contas a receber?"

**ANTES DO FIX** ❌:
- IA respondia: **9 contratos**
- Listava: 564/25A, 564/25B, **030/25**, **033/25**, **037/25**
- **Problema**: AHOLD COFFEE (030/25, 033/25, 037/25)
  - Têm `mesEmbarque = "2025/12"` (previsão de embarque)
  - MAS `contratos_embarcados = VAZIO` (não embarcaram de fato!)
  - Foram baixados em janeiro 2026
  - **NÃO deveriam estar na resposta**

**DEPOIS DO FIX** ✅:
- IA responde: **16 contratos**
- Lista: 382/25, 397/25, 406/25, 461/25, 474/25
- **Correto**: Apenas contratos que REALMENTE embarcaram (com `saidaNavio` preenchido)

## Causa Raiz

O sistema retornava TODOS os contratos com `mesEmbarque = "2025/12"` (data prevista), sem verificar se eles **efetivamente embarcaram** (campo `saidaNavio` preenchido).

## Solução Implementada

Adicionado **filtro automático** em `_format_results()` (linhas 1016-1023) que:

1. Detecta palavras-chave na pergunta:
   - "já foram embarcados"
   - "foram embarcados"
   - "que embarcaram"
   - "contratos embarcados"

2. Filtra apenas registros com `saidaNavio` preenchido (efetivamente embarcaram)

3. **Proteção**: Não aplica se mencionar "não embarcados" ou "sem embarque"

## Validação do Fix

✅ **TESTE LOCAL**:
```
Pergunta: "Dos contratos de dezembro de 2025 que já foram embarcados,
          quantos ainda não foram baixados no contas a receber?"

Resultado:
- Total de contratos dez/2025: 60
- Filtro aplicado: "embarcados (com saidaNavio) (60 → 47)"
- Contratos embarcados: 47
- Contratos embarcados NÃO baixados: 16 ✅ CORRETO

5 primeiros contratos:
1. 382/25 - THE DRIP CO.LTD
2. 397/25 - MIORI
3. 406/25 - MIORI
4. 461/25 - MIORI
5. 474/25 - UCC-COFFEE SERVICES
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
echo "=== Verificando FIX de filtro embarcados ==="
grep -A 8 "Filtro: embarcados (com data de saída do navio)" app/agents/sql_tools.py

# Deve retornar:
#   # Filtro: embarcados (com data de saída do navio)
#   # IMPORTANTE: Só aplica se a query menciona explicitamente "embarcados"
#   # E NÃO menciona "não embarcados" ou "sem embarque"
#   if any(term in query_lower for term in ["já foram embarcados", "foram embarcados", "que embarcaram", "contratos embarcados"]) and \
#      not any(term in query_lower for term in ["não embarcados", "não foram embarcados", "sem embarque", "não embarcaram"]):

# 6. Limpar cache do Python (IMPORTANTE!)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 7. Verificar sintaxe
python3 -m py_compile app/agents/sql_tools.py

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
Dos contratos de dezembro de 2025 que já foram embarcados,
quantos ainda não foram baixados no contas a receber?
Liste os 5 primeiros contratos e seus respectivos clientes.
```

**Resposta esperada**:
```
Foram encontrados 16 contratos de dezembro de 2025 que já foram
embarcados mas ainda não foram baixados no contas a receber.

Os 5 primeiros contratos são:

1. *382/25* - THE DRIP CO.LTD
2. *397/25* - MIORI
3. *406/25* - MIORI
4. *461/25* - MIORI
5. *474/25* - UCC-COFFEE SERVICES

[Mais detalhes...]
```

## Commits Relacionados

- **b5499f1**: Fix CRÍTICO: adicionar filtro automático para 'embarcados'
- **4379b0b**: Fix CRÍTICO: corrigir bug em queries sobre embarcados+baixados
- **3f7d5a9**: Fix CRÍTICO: ordenar orçamento por ESTOURO quando pergunta menciona 'estouraram'

## Arquivo Modificado

- [app/agents/sql_tools.py](app/agents/sql_tools.py#L1016-L1023)

## Troubleshooting

### Se o filtro não for aplicado:
```bash
# Verificar logs em tempo real enquanto faz a pergunta
journalctl -u agente-comexim -f --no-pager

# Procurar por:
# "[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados': 60 → 47"
```

### Se ainda retornar 9 contratos:
```bash
# Verificar se o cache foi limpo
find . -name "*.pyc" -o -name "__pycache__"

# Deve retornar vazio

# Se encontrar arquivos, limpar novamente e reiniciar
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
systemctl restart agente-comexim
```

### Se retornar contratos da AHOLD COFFEE:
```bash
# Significa que o fix não foi aplicado corretamente
# Verificar se o código está presente:
grep -c "já foram embarcados" app/agents/sql_tools.py

# Deve retornar: 1 ou mais
```
