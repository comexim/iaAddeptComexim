#!/bin/bash
# Script de deploy do fix de filtro automático para "embarcados"
# Commit: b5499f1

set -e  # Para se houver erro

echo "=========================================="
echo "DEPLOY: Fix Filtro Embarcados"
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

# 6. Verificar Fix (filtro embarcados)
echo ""
echo "5. Verificando FIX de filtro embarcados..."
if grep -q "já foram embarcados.*foram embarcados.*que embarcaram.*contratos embarcados" app/agents/sql_tools.py; then
    echo "   ✅ Fix PRESENTE"
    # Mostrar as linhas relevantes
    echo ""
    echo "   Código encontrado:"
    grep -A 3 "Filtro: embarcados" app/agents/sql_tools.py | head -n 5
else
    echo "   ❌ Fix AUSENTE!"
    exit 1
fi

# 7. Limpar cache
echo ""
echo "6. Limpando cache do Python..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Cache limpo"

# 8. Verificar sintaxe
echo ""
echo "7. Verificando sintaxe do Python..."
if python3 -m py_compile app/agents/sql_tools.py 2>/dev/null; then
    echo "   ✅ Sintaxe OK"
else
    echo "   ❌ ERRO DE SINTAXE!"
    python3 -m py_compile app/agents/sql_tools.py
    exit 1
fi

# 9. Reiniciar serviço
echo ""
echo "8. Reiniciando serviço..."
systemctl restart agente-comexim

# 10. Aguardar
echo ""
echo "9. Aguardando inicialização (10 segundos)..."
sleep 10

# 11. Verificar status
echo ""
echo "10. Status do serviço:"
systemctl status agente-comexim --no-pager -l | head -n 20

# 12. Logs recentes
echo ""
echo "11. Logs recentes (últimas 15 linhas):"
journalctl -u agente-comexim -n 15 --no-pager

echo ""
echo "=========================================="
echo "✅ DEPLOY CONCLUÍDO!"
echo "=========================================="
echo ""
echo "PRÓXIMO PASSO:"
echo "Teste no WhatsApp com a pergunta:"
echo ""
echo "  'Dos contratos de dezembro de 2025 que já foram"
echo "   embarcados, quantos ainda não foram baixados no"
echo "   contas a receber? Liste os 5 primeiros contratos"
echo "   e seus respectivos clientes.'"
echo ""
echo "Resposta esperada: 16 contratos, listando:"
echo "  1. 382/25 - THE DRIP CO.LTD"
echo "  2. 397/25 - MIORI"
echo "  3. 406/25 - MIORI"
echo "  4. 461/25 - MIORI"
echo "  5. 474/25 - UCC-COFFEE SERVICES"
echo ""
echo "IMPORTANTE: NÃO deve listar contratos da AHOLD COFFEE!"
echo ""
