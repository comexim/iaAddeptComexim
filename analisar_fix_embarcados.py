"""
Analisar o resultado após o fix de embarcados
"""
import json
import re

# Ler o arquivo
with open("resultado_fix_embarcados.txt", "r", encoding="utf-8") as f:
    content = f.read()

# Extrair o JSON array (formato não agregado)
# Primeiro, tentar encontrar dados agregados
if "Dados agregados:" in content:
    match = re.search(r'Dados agregados:\n\[(.*)\n\]', content, re.DOTALL)
    if match:
        json_str = '[' + match.group(1) + '\n]'
        data = json.loads(json_str)
        is_aggregated = True
    else:
        print("Não conseguiu extrair JSON agregado")
        exit(1)
else:
    # Formato não agregado
    match = re.search(r'Dados:\n\[(.*)\n\]', content, re.DOTALL)
    if match:
        json_str = '[' + match.group(1) + '\n]'
        data = json.loads(json_str)
        is_aggregated = False
    else:
        print("Não conseguiu extrair JSON")
        exit(1)

print("=" * 80)
print("ANÁLISE DO FIX DE EMBARCADOS")
print("=" * 80)
print()

if is_aggregated:
    print("Formato: AGREGADO por cliente")
    print()

    # Contar contratos não baixados
    nao_baixados_total = 0
    nao_baixados_por_cliente = []

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
            nao_baixados_total += len(nao_baixados)
            nao_baixados_por_cliente.append({
                'cliente': cliente,
                'total_nao_baixados': len(nao_baixados),
                'contratos': sorted(list(nao_baixados))
            })

    print(f"Total de contratos embarcados NÃO baixados: {nao_baixados_total}")
    print()
    print("Por cliente:")
    for item in sorted(nao_baixados_por_cliente, key=lambda x: x['total_nao_baixados'], reverse=True):
        print(f"  {item['cliente']}: {item['total_nao_baixados']} contratos")

    # Listar os 5 primeiros
    todos_nao_baixados = []
    for item in nao_baixados_por_cliente:
        for contrato in item['contratos']:
            todos_nao_baixados.append({
                'contrato': contrato,
                'cliente': item['cliente']
            })

    todos_nao_baixados.sort(key=lambda x: x['contrato'])

    print()
    print("=" * 80)
    print("5 PRIMEIROS CONTRATOS NÃO BAIXADOS:")
    print("=" * 80)
    for i, item in enumerate(todos_nao_baixados[:5], 1):
        print(f"{i}. {item['contrato']} ({item['cliente'].strip()})")

else:
    print("Formato: NÃO AGREGADO (lista completa)")
    print(f"Total de registros: {len(data)}")
    print()

    # Contar quantos têm saidaNavio
    com_saida = [r for r in data if r.get("saidaNavio") and str(r.get("saidaNavio")).strip()]
    print(f"Contratos com saidaNavio: {len(com_saida)}")

    # Verificar se algum deles foi baixado
    nao_baixados = []
    for r in com_saida:
        contrato = r.get("contrato", "").strip()

        # Verificar se foi baixado (tem baixaReceber preenchida)
        data_baixa = r.get("baixaReceber")
        if not data_baixa or str(data_baixa).strip() == "":
            nao_baixados.append({
                'contrato': contrato,
                'cliente': r.get("cliente", "").strip()
            })

    print(f"Contratos embarcados NÃO baixados: {len(nao_baixados)}")
    print()

    # Listar os 5 primeiros
    nao_baixados.sort(key=lambda x: x['contrato'])
    print("5 primeiros:")
    for i, item in enumerate(nao_baixados[:5], 1):
        print(f"{i}. {item['contrato']} ({item['cliente']})")

print()
print("=" * 80)
print("COMPARAÇÃO:")
print("=" * 80)
print("Esperado: 16 contratos embarcados NÃO baixados")
print(f"Obtido: {nao_baixados_total if is_aggregated else len(nao_baixados)} contratos")
print()
if (is_aggregated and nao_baixados_total == 16) or (not is_aggregated and len(nao_baixados) == 16):
    print("SUCESSO! O fix está funcionando corretamente!")
else:
    print("ATENÇÃO: Quantidade diferente do esperado")
