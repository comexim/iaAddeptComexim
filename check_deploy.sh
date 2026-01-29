#!/bin/bash
# Script para verificar e atualizar o servidor

echo "=========================================="
echo "VERIFICAÇÃO DO DEPLOY"
echo "=========================================="

# 1. Verificar branch atual
echo ""
echo "1. Branch atual:"
git branch --show-current

# 2. Verificar último commit local
echo ""
echo "2. Último commit local:"
git log --oneline -1

# 3. Verificar último commit remoto
echo ""
echo "3. Último commit remoto (origin/main):"
git log origin/main --oneline -1

# 4. Verificar se está atualizado
echo ""
echo "4. Status do repositório:"
git status

# 5. Verificar se o fix está no código
echo ""
echo "5. Verificando se o FIX está presente no código:"
if grep -q "FILTRADO AUTOMATICAMENTE" app/agents/sql_tools.py; then
    echo "[OK] Fix de múltiplos bancos PRESENTE"
else
    echo "[ERRO] Fix de múltiplos bancos AUSENTE"
fi

if grep -q "contratos_baixados_nov2025" app/agents/sql_tools.py; then
    echo "[OK] Fix de baixados nov/2025 PRESENTE"
else
    echo "[ERRO] Fix de baixados nov/2025 AUSENTE"
fi

# 6. Contar linhas do arquivo (para verificar se está atualizado)
echo ""
echo "6. Tamanho do arquivo sql_tools.py:"
wc -l app/agents/sql_tools.py

echo ""
echo "=========================================="
echo "AÇÕES NECESSÁRIAS"
echo "=========================================="
echo ""
echo "Se os FIXes estão AUSENTES, execute:"
echo "  1. git fetch origin"
echo "  2. git reset --hard origin/main"
echo "  3. systemctl restart agente-comexim  # ou o nome do seu serviço"
echo ""
echo "Se os FIXes estão PRESENTES, apenas reinicie:"
echo "  systemctl restart agente-comexim  # ou o nome do seu serviço"
echo ""
