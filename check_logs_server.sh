#!/bin/bash
echo "Cole este comando no servidor para ver os logs:"
echo ""
echo "journalctl -u agente-comexim -n 100 --no-pager -f"
echo ""
echo "Ou para ver só as últimas 50 linhas sem follow:"
echo "journalctl -u agente-comexim -n 50 --no-pager"
