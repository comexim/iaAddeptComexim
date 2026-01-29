"""
Teste do FIX: Detecção automática de múltiplos bancos na pergunta

Problema: IA omitiu Itaú Santos ao responder sobre "BB e Itaú Santos"
Solução: Filtro automático detecta bancos mencionados e mostra apenas esses
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions

print("="*70)
print("TESTE DO FIX: Detecção Automática de Múltiplos Bancos")
print("="*70)

user = UserPermissions(
    telefone="11999999999",
    nome="Test User",
    email="test@test.com",
    direitos=["Financeiro", "Vendas", "Compras", "Orçamento"]
)

sql_tools = SQLTools(user)

# Simular pergunta do usuário (EXATAMENTE como foi feita)
sql_tools.user_query = "Quanto tenho no total entre Banco do Brasil e Itaú Santos somando todas as moedas (reais, dólares e euros)?"

print(f"\nPergunta: {sql_tools.user_query}")
print("\n" + "-"*70)
print("Executando _pesquisa_saldo_bancario...")
print("-"*70)

result = sql_tools._pesquisa_saldo_bancario()

# Salvar resultado
with open("test_fix_saldo_result.txt", "w", encoding="utf-8") as f:
    f.write(result)

print("\n[OK] Resultado salvo em: test_fix_saldo_result.txt")

# Verificar se contém ambos os bancos
print("\n" + "="*70)
print("VERIFICAÇÃO DO FIX")
print("="*70)

tem_bb = "BB STOS" in result or "BB NY" in result or "Banco do Brasil" in result.upper()
tem_itau = "ITAU STOS" in result or "ITAÚ SANTOS" in result.upper()
tem_filtro = "FILTRADO AUTOMATICAMENTE" in result
tem_aviso = "QUANDO A PERGUNTA MENCIONA MÚLTIPLOS BANCOS" in result

print(f"\n[{'OK' if tem_filtro else 'ERRO'}] Filtro automático aplicado: {tem_filtro}")
print(f"[{'OK' if tem_bb else 'ERRO'}] BB encontrado na resposta: {tem_bb}")
print(f"[{'OK' if tem_itau else 'ERRO'}] ITAU STOS encontrado na resposta: {tem_itau}")
print(f"[{'OK' if tem_aviso else 'ERRO'}] Aviso sobre múltiplos bancos: {tem_aviso}")

if tem_filtro and tem_bb and tem_itau and tem_aviso:
    print("\n" + "="*70)
    print("[OK][OK][OK] FIX FUNCIONOU! [OK][OK][OK]")
    print("="*70)
    print("\nAgora a IA:")
    print("  1. [OK] Detecta automaticamente os bancos mencionados")
    print("  2. [OK] Filtra apenas BB STOS e ITAU STOS")
    print("  3. [OK] Mostra ambos na resposta")
    print("  4. [OK] Tem instruções claras sobre múltiplos bancos")
else:
    print("\n[ERRO] FIX NÃO FUNCIONOU COMPLETAMENTE")
    if not tem_filtro:
        print("  - Filtro automático não foi aplicado")
    if not tem_bb:
        print("  - BB não aparece na resposta")
    if not tem_itau:
        print("  - ITAU STOS não aparece na resposta")
    if not tem_aviso:
        print("  - Aviso sobre múltiplos bancos não foi adicionado")

# Extrair e mostrar os dados dos bancos
print("\n" + "="*70)
print("DADOS RETORNADOS")
print("="*70)

import re
import json

# Extrair JSON da resposta
match = re.search(r'\[[\s\S]*?\]', result)
if match:
    json_str = match.group()
    try:
        bancos_list = json.loads(json_str)

        print(f"\nTotal de bancos na resposta: {len(bancos_list)}")

        for banco in bancos_list:
            nome = banco.get('banco', '')
            moeda = banco.get('moeda', '')
            saldo = banco.get('saldo', 0)
            print(f"  - {nome:20} | {moeda:10} | Saldo: {saldo:>15,.2f}")
    except Exception as e:
        print(f"Erro ao parsear JSON: {e}")
