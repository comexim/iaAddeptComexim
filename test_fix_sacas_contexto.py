"""
Validar FIX: Query sobre sacas não deve usar contexto histórico
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions
from dotenv import load_dotenv

load_dotenv()

# Criar usuário com permissões
user = UserPermissions(
    telefone="teste",
    nome="Teste",
    email="teste@teste.com",
    direitos=["Vendas"],
    acesso_ia_vendas=True,
    acesso_ia_compras=True,
    acesso_ia_orcamento=True,
    acesso_ia_contas_a_pagar=True,
    acesso_ia_contas_a_receber=True,
    acesso_ia_saldo_bancario=True,
    acesso_ia_despesa_venda=True
)

# Criar tools
sql_tools = SQLTools(user)

print("=" * 80)
print("TESTE: Fix de contexto em query sobre sacas")
print("=" * 80)
print()

# SIMULA O QUE O ORCHESTRATOR FAZ:
# 1. Query anterior contextualizada (com "embarcados" e "baixados")
query_contextualizada = "Dos contratos de dezembro de 2025 que já foram embarcados, quantos ainda não foram baixados no contas a receber? Quantas sacas exportamos este mês?"

# 2. Query ORIGINAL (sem contexto)
query_original = "Quantas sacas exportamos este mês?"

# 3. Atribui ambas
sql_tools.user_query = query_contextualizada  # Contextualizada para IA entender
sql_tools.user_query_original = query_original  # Original para filtros

print(f"Query CONTEXTUALIZADA (para IA): '{query_contextualizada[:80]}...'")
print(f"Query ORIGINAL (para filtros): '{query_original}'")
print()
print("=" * 80)
print("VERIFICANDO...")
print("=" * 80)
print()

# Chamar a tool
resultado = sql_tools._pesquisa_vendas(periodo="este mês")

# Salvar resultado
with open("resultado_fix_sacas_contexto.txt", "w", encoding="utf-8") as f:
    f.write(resultado)

print(f"Resultado salvo em: resultado_fix_sacas_contexto.txt")
print(f"Tamanho: {len(resultado)} caracteres")
print()

# Verificar se NÃO aplicou filtro de embarcados
if "[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'" in resultado:
    print("[ERRO] Filtro de embarcados foi aplicado INCORRETAMENTE!")
    print("   O fix NÃO funcionou!")
else:
    print("[OK] Filtro de embarcados NÃO foi aplicado (correto!)")

# Verificar se NÃO forçou agregação
if "[AGREGAÇÃO FORÇADA] Padrão 'embarcados... (não) baixados' detectado" in resultado:
    print("[ERRO] Agregação forçada foi aplicada INCORRETAMENTE!")
    print("   O fix NÃO funcionou!")
else:
    print("[OK] Agregação forçada NÃO foi aplicada (correto!)")

# Verificar se NÃO calculou sumário especial
if "SUMÁRIO PARA ESTA QUERY ESPECÍFICA" in resultado:
    print("[ERRO] Sumário especial foi calculado INCORRETAMENTE!")
    print("   O fix NÃO funcionou!")
else:
    print("[OK] Sumário especial NÃO foi calculado (correto!)")

print()

# Procurar o total de sacas no resultado
import re

# Procurar por "Total de Sacas:" no formato agregado
match_total = re.search(r'Total de Sacas:\s*([\d,\.]+)', resultado)
if match_total:
    total_str = match_total.group(1).replace(',', '')
    total_sacas = float(total_str)
    print(f"[OK] Total de Sacas (encontrado na resposta): {total_sacas:,.2f}")
else:
    print("[X] Não encontrou 'Total de Sacas' na resposta")

    # Tentar somar manualmente dos dados JSON
    if "Dados agregados:" in resultado or '"total_sacas":' in resultado:
        print("\nTentando calcular manualmente dos dados JSON...")

        # Extrair todos os valores de total_sacas
        sacas_matches = re.findall(r'"total_sacas":\s*([\d\.]+)', resultado)
        if sacas_matches:
            total_manual = sum(float(s) for s in sacas_matches)
            print(f"[OK] Total calculado manualmente: {total_manual:,.2f}")
            total_sacas = total_manual
        else:
            print("[X] Não conseguiu extrair sacas dos dados")
            total_sacas = None
    else:
        # Formato não agregado
        print("\nDados no formato não agregado, somando campo 'sacas'...")
        sacas_matches = re.findall(r'"sacas":\s*([\d\.]+)', resultado)
        if sacas_matches:
            total_manual = sum(float(s) for s in sacas_matches)
            print(f"[OK] Total calculado: {total_manual:,.2f}")
            total_sacas = total_manual
        else:
            total_sacas = None

print()
print("=" * 80)
print("VALIDAÇÃO FINAL:")
print("=" * 80)
print(f"Esperado: 108.211,79 sacas")
if total_sacas:
    print(f"Obtido:   {total_sacas:,.2f} sacas")
    print()
    diferenca = abs(total_sacas - 108211.79)
    if diferenca < 1:
        print("[SUCESSO] FIX FUNCIONOU! Valor correto de sacas sem filtro incorreto!")
    else:
        print(f"[ERRO] Diferença de {diferenca:,.2f} sacas")
        print(f"   Percentual de erro: {(diferenca / 108211.79 * 100):.2f}%")
else:
    print("Obtido:   (não conseguiu calcular)")
