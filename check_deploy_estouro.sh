#!/bin/bash
# Script para verificar se o fix de estouro está ativo no servidor

echo "=========================================="
echo "VERIFICANDO FIX DE ESTOURO NO SERVIDOR"
echo "=========================================="

echo ""
echo "1. Verificando commit atual:"
echo "----------------------------------------"
git log -1 --oneline

echo ""
echo "2. Verificando se o código do fix está presente:"
echo "----------------------------------------"
echo "Buscando por 'ordenar_por_estouro' no código:"
grep -n "ordenar_por_estouro" app/agents/sql_tools.py | head -5

echo ""
echo "3. Verificando linha específica do fix:"
echo "----------------------------------------"
echo "Linha 894 deve conter 'ordenar_por_estouro = False':"
sed -n '894p' app/agents/sql_tools.py

echo ""
echo "4. Verificando detecção de palavras-chave:"
echo "----------------------------------------"
echo "Linha com detecção de 'estouro' (deve existir):"
grep -n "estouro.*estourou.*estouraram" app/agents/sql_tools.py

echo ""
echo "5. Status do serviço:"
echo "----------------------------------------"
systemctl status agente-comexim | head -10

echo ""
echo "6. Verificando se há processos Python antigos rodando:"
echo "----------------------------------------"
ps aux | grep "python.*app" | grep -v grep

echo ""
echo "=========================================="
echo "DIAGNÓSTICO"
echo "=========================================="
echo ""
echo "Se o código está presente MAS a IA ainda responde errado:"
echo "  1. Execute: systemctl restart agente-comexim"
echo "  2. Aguarde 10 segundos"
echo "  3. Teste novamente"
echo ""
echo "Se o código NÃO está presente:"
echo "  1. Verifique se está no branch correto: git branch"
echo "  2. Faça git pull novamente"
echo "  3. Verifique o commit: git log -1"
echo ""
