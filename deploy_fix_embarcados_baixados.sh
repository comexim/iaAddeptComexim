#!/bin/bash
# Script de deploy do fix de embarcados+baixados
# Commit: 4379b0b

set -e  # Para se houver erro

echo "=========================================="
echo "DEPLOY: Fix Embarcados+Baixados"
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

# 6. Verificar Fix 1 (proteção falsos clientes)
echo ""
echo "5. Verificando FIX 1 (proteção contra falsos positivos)..."
if grep -q "NÃO tenta extrair cliente se a query menciona operações" app/agents/sql_tools.py; then
    echo "   ✅ Fix 1 PRESENTE"
    # Mostrar um trecho
    grep -A 2 "palavras_operacao = \[" app/agents/sql_tools.py | head -n 5
else
    echo "   ❌ Fix 1 AUSENTE!"
    exit 1
fi

# 7. Verificar Fix 2 (desabilitar otimização)
echo ""
echo "6. Verificando FIX 2 (desabilitar otimização janeiro 2026)..."
if grep -q "if False and self.user_query" app/agents/sql_tools.py; then
    echo "   ✅ Fix 2 PRESENTE"
    # Mostrar a linha
    grep -B 1 "if False and self.user_query" app/agents/sql_tools.py | head -n 3
else
    echo "   ❌ Fix 2 AUSENTE!"
    exit 1
fi

# 8. Limpar cache
echo ""
echo "7. Limpando cache do Python..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Cache limpo"

# 9. Verificar sintaxe
echo ""
echo "8. Verificando sintaxe do Python..."
if python3 -m py_compile app/agents/sql_tools.py 2>/dev/null; then
    echo "   ✅ Sintaxe OK"
else
    echo "   ❌ ERRO DE SINTAXE!"
    python3 -m py_compile app/agents/sql_tools.py
    exit 1
fi

# 10. Reiniciar serviço
echo ""
echo "9. Reiniciando serviço..."
systemctl restart agente-comexim

# 11. Aguardar
echo ""
echo "10. Aguardando inicialização (10 segundos)..."
sleep 10

# 12. Verificar status
echo ""
echo "11. Status do serviço:"
systemctl status agente-comexim --no-pager -l | head -n 20

# 13. Logs recentes
echo ""
echo "12. Logs recentes (últimas 15 linhas):"
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
echo "Resposta esperada: ~59 contratos, listando:"
echo "  1. 382/25 - THE DRIP CO.LTD"
echo "  2. 397/25 - MIORI"
echo "  3. 406/25 - MIORI"
echo "  4. 443/25 - H A BENNETT"
echo "  5. 457/25 - H A BENNETT"
echo ""
