#!/bin/bash
# Script para extrair o erro real dos logs de produção

echo "=========================================="
echo "BUSCANDO ERRO REAL NOS LOGS"
echo "=========================================="

echo ""
echo "1. Procurando por 'Erro ao executar IA_SaldoBancario' nos últimos 200 logs:"
echo "----------------------------------------"
journalctl -u agente-comexim -n 200 --no-pager | grep -A 3 "Erro ao executar IA_SaldoBancario"

echo ""
echo "2. Procurando por linhas de ERRO nos últimos 100 logs:"
echo "----------------------------------------"
journalctl -u agente-comexim -n 100 --no-pager | grep -i "ERROR"

echo ""
echo "3. Procurando por exceções Python nos últimos 200 logs:"
echo "----------------------------------------"
journalctl -u agente-comexim -n 200 --no-pager | grep -E "(Traceback|Exception|Error:)" -A 5

echo ""
echo "4. Logs completos dos últimos 100 registros relacionados a saldo:"
echo "----------------------------------------"
journalctl -u agente-comexim -n 100 --no-pager | grep -i "saldo" -B 2 -A 2

echo ""
echo "=========================================="
echo "AÇÕES SUGERIDAS"
echo "=========================================="
echo ""
echo "Se não encontrou o erro acima, execute diretamente:"
echo "  1. cd /opt/agente-comexim-whatsapp"
echo "  2. source venv/bin/activate"
echo "  3. python3 debug_prod_error.py"
echo ""
echo "Isso mostrará o traceback completo do erro."
echo ""
