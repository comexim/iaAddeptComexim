# Deploy do Fix: Ordenação por Estouro no Orçamento

## Problema Corrigido

A IA estava reportando a **3ª categoria com maior estouro** incorretamente:
- **Reportava**: DESPESAS DE EXPORTAÇÃO (R$ 2,3M estouro) - posição #5 real
- **Deveria reportar**: CONSULTORIA (R$ 9,0M estouro) - posição #3 real

**Causa**: Dados eram ordenados por "valor orçado" ao invés de "valor do estouro" (realizado - orçado)

## Solução Implementada

Arquivo modificado: [app/agents/sql_tools.py](app/agents/sql_tools.py#L887-L906)

Agora detecta palavras-chave na pergunta:
- "estouro", "estourou", "estouraram", "estourar"
- "mais gastou", "excedeu"

Se detectado → ordena por **(realizado - orçado)**
Se NÃO detectado → ordena por **orçado** (padrão)

## Validação do Fix

✅ **TESTE 1** - Pergunta com "estouraram":
```
Pergunta: "Quais as 3 categorias que mais estouraram?"
Resultado:
  1. SEM ORCAMENTO (R$ 277M estouro)
  2. DESP FINANCEIRAS (R$ 19M estouro)
  3. CONSULTORIA (R$ 9M estouro) ✅ CORRETO
```

✅ **TESTE 2** - Pergunta SEM "estouro":
```
Pergunta: "Quais as maiores categorias do orçamento?"
Resultado:
  1. SERVICO DE APOIO (R$ 60M orçado)
  2. REMUNERACAO (R$ 12M orçado)
  3. DIVIDENDOS ORDINARIOS (R$ 9M orçado) ✅ CORRETO
```

## Deploy no Servidor

```bash
# 1. Conectar no servidor
ssh root@srv824573

# 2. Navegar para o diretório
cd /opt/agente-comexim-whatsapp

# 3. Fazer backup da versão atual
cp app/agents/sql_tools.py app/agents/sql_tools.py.backup_$(date +%Y%m%d_%H%M%S)

# 4. Puxar alterações do GitHub
git pull

# 5. Verificar se o fix está presente
grep -A 5 "DETECÇÃO: Se a pergunta menciona" app/agents/sql_tools.py

# Deve retornar algo como:
#   # DETECÇÃO: Se a pergunta menciona "estouro", ordena por ESTOURO (realizado - orçado)
#   # Caso contrário, ordena por valor orçado
#   ordenar_por_estouro = False

# 6. Limpar cache do Python
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 7. Reiniciar o serviço
systemctl restart agente-comexim

# 8. Verificar status
systemctl status agente-comexim

# 9. Verificar logs (aguardar ~10 segundos)
journalctl -u agente-comexim -n 20 --no-pager

# Procurar por: "ORDENAÇÃO] Pergunta menciona 'estouro'" nos logs
```

## Verificação Pós-Deploy

Fazer uma pergunta no WhatsApp:
```
Qual o percentual total realizado do orçamento de 2025 até agora?
E quais as 3 categorias que mais estouraram?
```

**Resposta esperada**:
- Percentual: 262,11%
- Top 3 que mais estouraram:
  1. SEM ORÇAMENTO: R$ 277.403.270,56
  2. DESPESAS FINANCEIRAS: R$ 19.022.135,18
  3. CONSULTORIA: R$ 9.656.350,55 ✅ CORRIGIDO

## Commit

- **Hash**: 3f7d5a9
- **Mensagem**: "Fix CRÍTICO: ordenar orçamento por ESTOURO quando pergunta menciona 'estouraram'"
- **Arquivo**: app/agents/sql_tools.py (linhas 887-906)
