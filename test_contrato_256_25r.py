#!/usr/bin/env python3
"""
Teste: Verificar contrato 256/25R no contas a receber para 9 de fevereiro de 2026
"""
import sys
sys.path.insert(0, '/opt/agente-comexim-whatsapp')

from app.core.database import SQLServerClient

print("="*80)
print("TESTE: Contrato 256/25R no contas a receber - 9 de fevereiro de 2026")
print("="*80)

client = SQLServerClient()

# Busca todas contas a receber para 9 de fevereiro de 2026
print("\n[1] Buscando TODAS contas a receber para 2026-02-09...")
all_results = client.execute_function("IA_ContasAReceber", filters={"vencimentoReal": "20260209"})
print(f"Total encontrados: {len(all_results)}")

# Filtra pelo contrato 256/25R
contrato_target = "256/25R"
print(f"\n[2] Filtrando por contrato '{contrato_target}'...")

# Função auxiliar para normalizar contrato (mesma lógica do sql_tools.py)
def normalizar_contrato(contrato_str):
    """Normaliza contrato removendo zeros à esquerda: '000256/25R' -> '256/25R'"""
    if not contrato_str or not isinstance(contrato_str, str):
        return ""

    partes = contrato_str.strip().split('/')
    if len(partes) >= 2:
        # Remove zeros à esquerda da primeira parte
        numero = partes[0].lstrip('0') or '0'
        sufixo = '/'.join(partes[1:])
        return f"{numero}/{sufixo}"
    return contrato_str.strip()

contrato_normalizado = normalizar_contrato(contrato_target)
print(f"Contrato normalizado: '{contrato_normalizado}'")

filtered = [r for r in all_results if normalizar_contrato(str(r.get("contrato", ""))) == contrato_normalizado]
print(f"Total encontrados para contrato {contrato_target}: {len(filtered)}")

if filtered:
    print(f"\n[3] Detalhes dos {len(filtered)} títulos encontrados:")
    total_valor = 0
    total_saldo = 0

    for i, r in enumerate(filtered, 1):
        cliente = r.get('cliente', 'N/A')
        numero = r.get('numero', 'N/A')
        parcela = r.get('parcela', 'N/A')
        valor = float(r.get('valor', 0) or 0)
        saldo = float(r.get('saldo', 0) or 0)
        vencimento = r.get('vencimentoReal', 'N/A')

        total_valor += valor
        total_saldo += saldo

        print(f"\n  Título {i}:")
        print(f"    Cliente: {cliente}")
        print(f"    Número: {numero}, Parcela: {parcela}")
        print(f"    Valor: R$ {valor:,.2f}")
        print(f"    Saldo: R$ {saldo:,.2f}")
        print(f"    Vencimento: {vencimento}")

    print(f"\n  TOTAIS:")
    print(f"    Valor total: R$ {total_valor:,.2f}")
    print(f"    Saldo total: R$ {total_saldo:,.2f}")
else:
    print("\n❌ NENHUM título encontrado para o contrato 256/25R")

    # Debug: mostra quais contratos existem para a data
    contratos_unicos = set()
    for r in all_results:
        contrato = r.get('contrato', '')
        if contrato:
            contratos_unicos.add(contrato)

    print(f"\n[DEBUG] Contratos encontrados para 2026-02-09 ({len(contratos_unicos)} únicos):")
    for c in sorted(contratos_unicos)[:20]:
        print(f"  - '{c}' (normalizado: '{normalizar_contrato(c)}')")

print("\n" + "="*80)
