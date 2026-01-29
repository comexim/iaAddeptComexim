"""
Contar contratos não baixados no formato AGREGADO
"""
import json
import re

# Ler o arquivo
with open("resultado_fix_embarcados.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Extrair o JSON agregado
match = re.search(r'Dados agregados:\n\[(.*)\n\]', content, re.DOTALL)
if not match:
    print("Não encontrou JSON agregado")
    exit(1)

json_str = '[' + match.group(1) + '\n]'
data = json.loads(json_str)

print("=" * 80)
print("ANÁLISE DE CONTRATOS NÃO BAIXADOS (FORMATO AGREGADO)")
print("=" * 80)
print()

# Contar contratos não baixados
total_nao_baixados = 0
detalhes = []

for cliente_data in data:
    cliente = cliente_data.get("cliente", "").strip()

    # Contratos embarcados
    embarcados_str = cliente_data.get("contratos_embarcados", "")
    embarcados = set()
    if embarcados_str:
        for c in embarcados_str.split(','):
            c = c.strip()
            if c:
                embarcados.add(c)

    # Contratos baixados em qualquer mês
    baixados = set()
    for campo in ['contratos_baixados_nov2025', 'contratos_baixados_dez2025', 'contratos_baixados_jan2026']:
        baixados_str = cliente_data.get(campo, "")
        if baixados_str:
            for c in baixados_str.split(','):
                c = c.strip()
                if c:
                    baixados.add(c)

    # Não baixados
    nao_baixados = embarcados - baixados

    if len(nao_baixados) > 0:
        total_nao_baixados += len(nao_baixados)
        detalhes.append({
            'cliente': cliente,
            'total': len(nao_baixados),
            'contratos': sorted(list(nao_baixados))
        })

print(f"Total de contratos embarcados NÃO baixados: {total_nao_baixados}")
print()

detalhes.sort(key=lambda x: x['total'], reverse=True)
print("Por cliente:")
for item in detalhes:
    print(f"  {item['cliente']}: {item['total']} contratos - {', '.join(item['contratos'][:3])}")

# Listar os 5 primeiros
print()
print("=" * 80)
print("5 PRIMEIROS CONTRATOS NÃO BAIXADOS:")
print("=" * 80)

todos = []
for item in detalhes:
    for c in item['contratos']:
        todos.append({'contrato': c, 'cliente': item['cliente']})

todos.sort(key=lambda x: x['contrato'])

for i, item in enumerate(todos[:5], 1):
    print(f"{i}. {item['contrato']} ({item['cliente']})")

print()
print("=" * 80)
print("VALIDAÇÃO:")
print("=" * 80)
print(f"Esperado: 16 contratos")
print(f"Obtido: {total_nao_baixados} contratos")
if total_nao_baixados == 16:
    print("SUCESSO! A agregação está retornando os dados corretos!")
else:
    print(f"ATENÇÃO: Diferença de {abs(16 - total_nao_baixados)} contratos")
