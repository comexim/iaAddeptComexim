"""
Validação: Saldo total entre Banco do Brasil e Itaú Santos (todas as moedas)

Pergunta: "Quanto tenho no total entre Banco do Brasil e Itaú Santos
          somando todas as moedas (reais, dólares e euros)?"

Resposta da IA:
- Banco do Brasil:
  - Reais: R$ 67.988,96
  - Dólares: R$ 841,41

(A resposta está INCOMPLETA - falta euros do BB e TODO o Itaú Santos)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions

print("="*70)
print("VALIDAÇÃO: Saldo BB + Itaú Santos (todas as moedas)")
print("="*70)

# 1. Buscar dados DIRETO do banco
print("\n1. VERIFICAÇÃO DIRETA NO BANCO DE DADOS")
print("-"*70)

result_all = sql_client.execute_function("IA_SaldoBancario", {})

# Filtrar Banco do Brasil e Itaú Santos
# Nota: No banco, aparece como "BB STOS" e "ITAU STOS"
bb_contas = [r for r in result_all if "BB" in r.get("banco", "").upper() and ("STOS" in r.get("banco", "").upper() or "NY" in r.get("banco", "").upper())]
itau_santos_contas = [r for r in result_all if "ITAU" in r.get("banco", "").upper() and "STOS" in r.get("banco", "").upper()]

print(f"\nContas encontradas:")
print(f"  - Banco do Brasil: {len(bb_contas)} conta(s)")
print(f"  - Itaú Santos: {len(itau_santos_contas)} conta(s)")

# Banco do Brasil
print("\n" + "="*70)
print("BANCO DO BRASIL - Saldos por Moeda")
print("="*70)

bb_reais = 0
bb_dolares = 0
bb_euros = 0

for conta in bb_contas:
    banco = conta.get("banco", "").strip()
    agencia = conta.get("agencia", "").strip()
    conta_num = conta.get("conta", "").strip()
    moeda = conta.get("moeda", "").strip()
    saldo = float(conta.get("saldo", 0) or 0)

    print(f"\n  Banco: {banco}")
    print(f"  Agência: {agencia}, Conta: {conta_num}")
    print(f"  Moeda: {moeda}, Saldo: {saldo:,.2f}")

    moeda_upper = moeda.upper()
    if moeda_upper in ["R$", "REAIS", "BRL"]:
        bb_reais += saldo
    elif moeda_upper in ["US$", "USD", "DOLAR", "DOLARES", "DÓLAR", "DÓLARES"]:
        bb_dolares += saldo
    elif moeda_upper in ["EUR", "EURO", "EUROS", "€"]:
        bb_euros += saldo

print("\n" + "-"*70)
print("TOTAIS BANCO DO BRASIL:")
print(f"  Reais:   R$ {bb_reais:,.2f}")
print(f"  Dólares: US$ {bb_dolares:,.2f}")
print(f"  Euros:   € {bb_euros:,.2f}")

# Itaú Santos
print("\n" + "="*70)
print("ITAÚ SANTOS - Saldos por Moeda")
print("="*70)

itau_reais = 0
itau_dolares = 0
itau_euros = 0

for conta in itau_santos_contas:
    banco = conta.get("banco", "").strip()
    agencia = conta.get("agencia", "").strip()
    conta_num = conta.get("conta", "").strip()
    moeda = conta.get("moeda", "").strip()
    saldo = float(conta.get("saldo", 0) or 0)

    print(f"\n  Banco: {banco}")
    print(f"  Agência: {agencia}, Conta: {conta_num}")
    print(f"  Moeda: {moeda}, Saldo: {saldo:,.2f}")

    moeda_upper = moeda.upper()
    if moeda_upper in ["R$", "REAIS", "BRL"]:
        itau_reais += saldo
    elif moeda_upper in ["US$", "USD", "DOLAR", "DOLARES", "DÓLAR", "DÓLARES"]:
        itau_dolares += saldo
    elif moeda_upper in ["EUR", "EURO", "EUROS", "€"]:
        itau_euros += saldo

print("\n" + "-"*70)
print("TOTAIS ITAÚ SANTOS:")
print(f"  Reais:   R$ {itau_reais:,.2f}")
print(f"  Dólares: US$ {itau_dolares:,.2f}")
print(f"  Euros:   € {itau_euros:,.2f}")

# TOTAL GERAL
print("\n" + "="*70)
print("TOTAL GERAL (BB + ITAÚ SANTOS)")
print("="*70)

total_reais = bb_reais + itau_reais
total_dolares = bb_dolares + itau_dolares
total_euros = bb_euros + itau_euros

print(f"  Reais:   R$ {total_reais:,.2f}")
print(f"  Dólares: US$ {total_dolares:,.2f}")
print(f"  Euros:   € {total_euros:,.2f}")

# 2. Testar o que a IA vê
print("\n" + "="*70)
print("2. DADOS DA AGREGAÇÃO (o que a IA vê)")
print("="*70)

user = UserPermissions(
    telefone="11999999999",
    nome="Test User",
    email="test@test.com",
    direitos=["Financeiro", "Vendas", "Compras", "Orçamento"]
)

sql_tools = SQLTools(user)
sql_tools.user_query = "Quanto tenho no total entre Banco do Brasil e Itaú Santos somando todas as moedas (reais, dólares e euros)?"

result = sql_tools._pesquisa_saldo_bancario()

# Salvar resultado para análise
with open("test_saldo_bb_itau_result.txt", "w", encoding="utf-8") as f:
    f.write(str(result))

print("\nResultado salvo em: test_saldo_bb_itau_result.txt")
print(f"Tipo de resultado: {type(result)}")

# 3. VALIDAÇÃO DA RESPOSTA DA IA
print("\n" + "="*70)
print("3. VALIDAÇÃO DA RESPOSTA DA IA")
print("="*70)

print("\nRESPOSTA DA IA (fornecida pelo usuário):")
print("  Banco do Brasil:")
print("    - Reais: R$ 67.988,96")
print("    - Dólares: R$ 841,41")
print("  (Resposta INCOMPLETA - falta euros e Itaú Santos)")

print("\n" + "-"*70)
print("DADOS REAIS DO BANCO:")
print("-"*70)
print("\nBanco do Brasil:")
print(f"  - Reais:   R$ {bb_reais:,.2f}")
print(f"  - Dólares: US$ {bb_dolares:,.2f}")
print(f"  - Euros:   € {bb_euros:,.2f}")

print("\nItaú Santos:")
print(f"  - Reais:   R$ {itau_reais:,.2f}")
print(f"  - Dólares: US$ {itau_dolares:,.2f}")
print(f"  - Euros:   € {itau_euros:,.2f}")

print("\nTOTAL GERAL:")
print(f"  - Reais:   R$ {total_reais:,.2f}")
print(f"  - Dólares: US$ {total_dolares:,.2f}")
print(f"  - Euros:   € {total_euros:,.2f}")

# Comparação
print("\n" + "="*70)
print("RESULTADO DA VALIDAÇÃO")
print("="*70)

# Verificar BB Reais
ia_bb_reais = 67988.96
if abs(bb_reais - ia_bb_reais) < 0.01:
    print("[OK] BB Reais: CORRETO")
    print(f"     IA: R$ {ia_bb_reais:,.2f} | Banco: R$ {bb_reais:,.2f}")
else:
    print("[ERRO] BB Reais: INCORRETO")
    print(f"       IA: R$ {ia_bb_reais:,.2f} | Banco: R$ {bb_reais:,.2f}")
    print(f"       Diferença: R$ {abs(bb_reais - ia_bb_reais):,.2f}")

# Verificar BB Dólares
ia_bb_dolares = 841.41
if abs(bb_dolares - ia_bb_dolares) < 0.01:
    print("[OK] BB Dólares: CORRETO")
    print(f"     IA: US$ {ia_bb_dolares:,.2f} | Banco: US$ {bb_dolares:,.2f}")
else:
    print("[ERRO] BB Dólares: INCORRETO")
    print(f"       IA: US$ {ia_bb_dolares:,.2f} | Banco: US$ {bb_dolares:,.2f}")
    print(f"       Diferença: US$ {abs(bb_dolares - ia_bb_dolares):,.2f}")

# Verificar se mencionou euros do BB
print("\n[ERRO] BB Euros: NÃO MENCIONADO pela IA")
if bb_euros > 0:
    print(f"       Banco tem: € {bb_euros:,.2f}")
else:
    print(f"       Banco tem: € 0,00 (não há euros no BB)")

# Verificar se mencionou Itaú Santos
print("\n[ERRO] ITAÚ SANTOS: NÃO MENCIONADO pela IA")
print(f"       Reais:   R$ {itau_reais:,.2f}")
print(f"       Dólares: US$ {itau_dolares:,.2f}")
print(f"       Euros:   € {itau_euros:,.2f}")

# Conclusão
print("\n" + "="*70)
print("CONCLUSÃO")
print("="*70)

problemas = []
if abs(bb_reais - ia_bb_reais) >= 0.01:
    problemas.append("BB Reais incorreto")
if abs(bb_dolares - ia_bb_dolares) >= 0.01:
    problemas.append("BB Dólares incorreto")
if bb_euros != 0:
    problemas.append(f"BB Euros não mencionado (€ {bb_euros:,.2f})")
# CRÍTICO: Verificar se Itaú Santos tem QUALQUER saldo (positivo OU negativo)
if itau_reais != 0 or itau_dolares != 0 or itau_euros != 0:
    problemas.append(f"Itaú Santos COMPLETAMENTE OMITIDO (R$ {itau_reais:,.2f})")

if len(problemas) == 0:
    print("\n[OK] RESPOSTA DA IA ESTÁ CORRETA!")
else:
    print("\n[ERRO] RESPOSTA DA IA ESTÁ INCORRETA!")
    print("\nProblemas encontrados:")
    for i, problema in enumerate(problemas, 1):
        print(f"  {i}. {problema}")

    print("\nRESPOSTA CORRETA deveria ser:")
    print(f"\n  Banco do Brasil:")
    print(f"    - Reais:   R$ {bb_reais:,.2f}")
    print(f"    - Dólares: US$ {bb_dolares:,.2f}")
    if bb_euros > 0:
        print(f"    - Euros:   € {bb_euros:,.2f}")
    print(f"\n  Itaú Santos:")
    print(f"    - Reais:   R$ {itau_reais:,.2f}")
    print(f"    - Dólares: US$ {itau_dolares:,.2f}")
    if itau_euros > 0:
        print(f"    - Euros:   € {itau_euros:,.2f}")
    print(f"\n  TOTAL GERAL:")
    print(f"    - Reais:   R$ {total_reais:,.2f}")
    print(f"    - Dólares: US$ {total_dolares:,.2f}")
    if total_euros > 0:
        print(f"    - Euros:   € {total_euros:,.2f}")
