"""
Verifica campos disponíveis em IA_Vendas
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import sql_client

sql_client.test_connection()
results = sql_client.execute_function('IA_Vendas', {'mesEmbarque': '2026/01'})

if results:
    print('Campos disponíveis no primeiro registro:')
    primeiro = results[0]
    for key in sorted(primeiro.keys()):
        valor = primeiro[key]
        if valor is not None and str(valor).strip():
            print(f'  {key}: {valor}')

sql_client.close()
