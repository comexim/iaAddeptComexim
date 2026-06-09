#!/bin/bash
# Script para verificar erros de consulta de vendas

echo "=== LOGS RECENTES DO AGENTE (últimos 100 linhas) ==="
sudo journalctl -u agente-comexim -n 100 --no-pager

echo ""
echo "=== FILTRANDO APENAS ERROS ==="
sudo journalctl -u agente-comexim -n 200 --no-pager | grep -i "erro\|error\|exception\|traceback"

echo ""
echo "=== FILTRANDO ERROS DE VENDAS ==="
sudo journalctl -u agente-comexim -n 500 --no-pager | grep -i "vendas\|IA_Vendas" | grep -i "erro\|error"
