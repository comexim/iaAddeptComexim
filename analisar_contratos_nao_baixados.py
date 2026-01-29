"""
Analisar o resultado da tool para contar contratos NÃO baixados
"""
import json
import re

# Ler o arquivo
with open("resultado_ia_dezembro_2025.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Extrair o JSON array
match = re.search(r'Dados agregados:\n\[(.*)\n\]', content, re.DOTALL)
if not match:
    print("Não encontrou JSON")
    exit(1)

json_str = '[' + match.group(1) + '\n]'

# Parse JSON
try:
    data = json.loads(json_str)
except json.JSONDecodeError as e:
    print(f"Erro ao fazer parse do JSON: {e}")
    print("Tentando salvar o que foi extraído...")
    with open("json_extraido.txt", "w", encoding="utf-8") as f:
        f.write(json_str)
    exit(1)

print("=" * 80)
print("ANÁLISE DE CONTRATOS NÃO BAIXADOS")
print("=" * 80)
print()

# Contar contratos não baixados por cliente
nao_baixados_por_cliente = []

for cliente_data in data:
    cliente = cliente_data.get("cliente", "").strip()

    # Contratos embarcados (lista completa)
    embarcados_str = cliente_data.get("contratos_embarcados", "")
    embarcados = set()
    if embarcados_str:
        for c in embarcados_str.split(','):
            c = c.strip()
            if c:
                embarcados.add(c)

    # Contratos baixados em qualquer mês
    baixados = set()

    # Baixados em novembro
    baixados_nov = cliente_data.get("contratos_baixados_nov2025", "")
    if baixados_nov:
        for c in baixados_nov.split(','):
            c = c.strip()
            if c:
                baixados.add(c)

    # Baixados em dezembro
    baixados_dez = cliente_data.get("contratos_baixados_dez2025", "")
    if baixados_dez:
        for c in baixados_dez.split(','):
            c = c.strip()
            if c:
                baixados.add(c)

    # Baixados em janeiro
    baixados_jan = cliente_data.get("contratos_baixados_jan2026", "")
    if baixados_jan:
        for c in baixados_jan.split(','):
            c = c.strip()
            if c:
                baixados.add(c)

    # Calcular não baixados
    nao_baixados = embarcados - baixados

    if len(nao_baixados) > 0:
        nao_baixados_por_cliente.append({
            'cliente': cliente,
            'total_embarcados': len(embarcados),
            'total_baixados': len(baixados),
            'total_nao_baixados': len(nao_baixados),
            'nao_baixados': sorted(list(nao_baixados))
        })

# Ordenar por número de contratos não baixados (maior primeiro)
nao_baixados_por_cliente.sort(key=lambda x: x['total_nao_baixados'], reverse=True)

# Mostrar resumo
print("CLIENTES COM CONTRATOS NÃO BAIXADOS:")
print()
total_nao_baixados_global = 0
for item in nao_baixados_por_cliente:
    total_nao_baixados_global += item['total_nao_baixados']
    print(f"• {item['cliente']}")
    print(f"  Embarcados: {item['total_embarcados']} | Baixados: {item['total_baixados']} | NÃO Baixados: {item['total_nao_baixados']}")
    print(f"  Contratos não baixados: {', '.join(item['nao_baixados'])}")
    print()

print("=" * 80)
print(f"TOTAL: {total_nao_baixados_global} contratos embarcados em dezembro 2025 NÃO baixados")
print("=" * 80)
print()

# Listar os primeiros 5 contratos não baixados (ordenados por número de contrato)
todos_nao_baixados = []
for item in nao_baixados_por_cliente:
    for contrato in item['nao_baixados']:
        todos_nao_baixados.append({
            'contrato': contrato,
            'cliente': item['cliente']
        })

# Ordenar por número de contrato
todos_nao_baixados.sort(key=lambda x: x['contrato'])

print("=" * 80)
print("5 PRIMEIROS CONTRATOS NÃO BAIXADOS (ordenados por número):")
print("=" * 80)
for i, item in enumerate(todos_nao_baixados[:5], 1):
    print(f"{i}. {item['contrato']} ({item['cliente'].strip()})")

print()
print("=" * 80)
print("COMPARAÇÃO COM RESPOSTA DA IA:")
print("=" * 80)
print()
print("IA disse: 9 contratos")
print(f"Real: {total_nao_baixados_global} contratos")
print()
print("IA listou:")
print("1. 564/25A (THE FOLGER COFFEE)")
print("2. 564/25B (THE FOLGER COFFEE)")
print("3. 030/25 (AHOLD COFFEE)")
print("4. 033/25 (AHOLD COFFEE)")
print("5. 037/25 (AHOLD COFFEE)")
print()
print("Deveria listar:")
for i, item in enumerate(todos_nao_baixados[:5], 1):
    print(f"{i}. {item['contrato']} ({item['cliente'].strip()})")

# Verificar se os contratos da IA estão corretos
print()
print("=" * 80)
print("OS CONTRATOS QUE A IA LISTOU ESTÃO CORRETOS?")
print("=" * 80)
contratos_ia = ['564/25A', '564/25B', '030/25', '033/25', '037/25']
contratos_reais = [c['contrato'] for c in todos_nao_baixados]

for c_ia in contratos_ia:
    if c_ia in contratos_reais:
        print(f"✅ {c_ia} - SIM, está na lista de não baixados")
    else:
        print(f"❌ {c_ia} - NÃO está na lista de não baixados")
