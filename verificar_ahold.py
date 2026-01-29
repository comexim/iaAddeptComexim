"""
Verificar contratos da AHOLD COFFEE
"""
import json
import re

# Ler o arquivo
with open("resultado_ia_dezembro_2025.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Extrair o JSON array
match = re.search(r'Dados agregados:\n\[(.*)\n\]', content, re.DOTALL)
json_str = '[' + match.group(1) + '\n]'
data = json.loads(json_str)

# Procurar AHOLD COFFEE
for cliente_data in data:
    cliente = cliente_data.get("cliente", "").strip()
    if "AHOLD" in cliente:
        print("=" * 80)
        print(f"Cliente: {cliente}")
        print("=" * 80)
        print()
        print(f"Contratos: {cliente_data.get('contratos', '')}")
        print(f"Contratos embarcados: {cliente_data.get('contratos_embarcados', '')}")
        print(f"Contratos baixados (geral): {cliente_data.get('contratos_baixados', '')}")
        print(f"Contratos baixados nov2025: {cliente_data.get('contratos_baixados_nov2025', '')}")
        print(f"Contratos baixados dez2025: {cliente_data.get('contratos_baixados_dez2025', '')}")
        print(f"Contratos baixados jan2026: {cliente_data.get('contratos_baixados_jan2026', '')}")
        print()
        print(f"Total contratos: {cliente_data.get('total_contratos', 0)}")
        print(f"Total embarcados: {cliente_data.get('total_contratos_embarcados', 0)}")
        print(f"Total baixados: {cliente_data.get('total_contratos_baixados', 0)}")
        print()

        # Analisar quais não foram baixados
        embarcados = set()
        for c in cliente_data.get('contratos_embarcados', '').split(','):
            c = c.strip()
            if c:
                embarcados.add(c)

        baixados = set()
        for campo in ['contratos_baixados_nov2025', 'contratos_baixados_dez2025', 'contratos_baixados_jan2026']:
            for c in cliente_data.get(campo, '').split(','):
                c = c.strip()
                if c:
                    baixados.add(c)

        nao_baixados = embarcados - baixados
        print(f"Contratos NÃO baixados: {sorted(list(nao_baixados))}")
        print(f"Total NÃO baixados: {len(nao_baixados)}")
