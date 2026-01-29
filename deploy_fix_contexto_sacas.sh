#!/bin/bash
# Script de deploy do fix de contexto em queries de sacas
# Commit: dba6fa6

set -e  # Para se houver erro

echo "=========================================="
echo "DEPLOY: Fix Contexto em Query de Sacas"
echo "=========================================="

# 1. Verificar se está no diretório correto
if [ ! -f "app/agents/sql_tools.py" ]; then
    echo "❌ ERRO: Não está no diretório correto!"
    echo "Execute: cd /opt/agente-comexim-whatsapp"
    exit 1
fi

# 2. Verificar branch
echo ""
echo "1. Branch atual:"
BRANCH=$(git branch --show-current)
echo "   $BRANCH"
if [ "$BRANCH" != "main" ]; then
    echo "⚠️  AVISO: Não está na branch main!"
fi

# 3. Status antes do pull
echo ""
echo "2. Commit atual:"
git log --oneline -1

# 4. Pull
echo ""
echo "3. Puxando alterações do GitHub..."
git pull

# 5. Verificar commit após pull
echo ""
echo "4. Commit após pull:"
git log --oneline -1

# 6. Verificar Fix 1 (user_query_original declarado)
echo ""
echo "5. Verificando FIX de query original em sql_tools.py..."
if grep -q "self.user_query_original = \"\"" app/agents/sql_tools.py; then
    echo "   ✅ Declaração PRESENTE"
else
    echo "   ❌ Declaração AUSENTE!"
    exit 1
fi

# 7. Verificar Fix 2 (orchestrator passa query original)
echo ""
echo "6. Verificando FIX em orchestrator.py..."
if grep -q "sql_tools.user_query_original = message" app/agents/orchestrator.py; then
    echo "   ✅ Atribuição PRESENTE"
else
    echo "   ❌ Atribuição AUSENTE!"
    exit 1
fi

# 8. Contar quantos padrões foram corrigidos
echo ""
echo "7. Contando padrões corrigidos..."
COUNT=$(grep -c "user_query_original" app/agents/sql_tools.py || true)
echo "   Encontradas $COUNT referências a 'user_query_original'"
if [ "$COUNT" -ge 14 ]; then
    echo "   ✅ Quantidade OK (esperado: 14+)"
else
    echo "   ⚠️  AVISO: Esperado pelo menos 14 referências!"
fi

# 9. Verificar se NÃO há mais user_query em padrões críticos
echo ""
echo "8. Verificando se padrões críticos foram corrigidos..."
# Não deve encontrar "self.user_query.lower()" em contextos de detecção
# (exceto se for user_query_original)
WRONG_PATTERNS=$(grep -n "if.*self\.user_query\s*and.*re\.search" app/agents/sql_tools.py | grep -v "user_query_original" | wc -l || true)
if [ "$WRONG_PATTERNS" -eq 0 ]; then
    echo "   ✅ Nenhum padrão incorreto encontrado"
else
    echo "   ⚠️  AVISO: Encontrados $WRONG_PATTERNS padrões que ainda usam user_query"
    grep -n "if.*self\.user_query\s*and.*re\.search" app/agents/sql_tools.py | grep -v "user_query_original" || true
fi

# 10. Limpar cache
echo ""
echo "9. Limpando cache do Python..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Cache limpo"

# 11. Verificar sintaxe
echo ""
echo "10. Verificando sintaxe do Python..."
if python3 -m py_compile app/agents/sql_tools.py 2>/dev/null && python3 -m py_compile app/agents/orchestrator.py 2>/dev/null; then
    echo "   ✅ Sintaxe OK"
else
    echo "   ❌ ERRO DE SINTAXE!"
    python3 -m py_compile app/agents/sql_tools.py
    python3 -m py_compile app/agents/orchestrator.py
    exit 1
fi

# 12. Reiniciar serviço
echo ""
echo "11. Reiniciando serviço..."
systemctl restart agente-comexim

# 13. Aguardar
echo ""
echo "12. Aguardando inicialização (10 segundos)..."
sleep 10

# 14. Verificar status
echo ""
echo "13. Status do serviço:"
systemctl status agente-comexim --no-pager -l | head -n 20

# 15. Logs recentes
echo ""
echo "14. Logs recentes (últimas 15 linhas):"
journalctl -u agente-comexim -n 15 --no-pager

echo ""
echo "=========================================="
echo "✅ DEPLOY CONCLUÍDO!"
echo "=========================================="
echo ""
echo "PRÓXIMO PASSO:"
echo "Teste no WhatsApp com a pergunta:"
echo ""
echo "  'Quantas sacas exportamos este mês?'"
echo ""
echo "Resposta esperada: ~108.211,79 sacas"
echo ""
echo "IMPORTANTE: NÃO deve aparecer nos logs:"
echo "  - [FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'"
echo "  - [AGREGAÇÃO FORÇADA] Padrão 'embarcados... (não) baixados'"
echo "  - [SUMÁRIO ESPECIAL] Calculado: X contratos"
echo ""
