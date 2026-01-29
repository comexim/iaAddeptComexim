"""
Validar: Quantas sacas exportamos este mês (janeiro 2026)?
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

# Simular a pergunta
pergunta = "Quantas sacas exportamos este mês?"

# Armazenar a pergunta (a IA faz isso)
sql_tools.user_query = pergunta

print("=" * 80)
print("VALIDAÇÃO: Sacas exportadas este mês (janeiro 2026)")
print("=" * 80)
print()
print(f"Pergunta: {pergunta}")
print()
print("Resposta da IA: 81.834,82 sacas")
print()
print("=" * 80)
print("VERIFICANDO...")
print("=" * 80)
print()

# A IA deve chamar com "este mês" que o date_parser converte para janeiro 2026
resultado = sql_tools._pesquisa_vendas(periodo="este mês")

# Salvar resultado
with open("resultado_sacas_este_mes.txt", "w", encoding="utf-8") as f:
    f.write(resultado)

print(f"Resultado salvo em: resultado_sacas_este_mes.txt")
print(f"Tamanho: {len(resultado)} caracteres")
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
print("COMPARAÇÃO:")
print("=" * 80)
print(f"IA respondeu: 81.834,82 sacas")
if total_sacas:
    print(f"Real:        {total_sacas:,.2f} sacas")
    print()
    diferenca = abs(total_sacas - 81834.82)
    if diferenca < 0.1:
        print("[SUCESSO] CORRETO! Os valores coincidem.")
    else:
        print(f"[ERRO] ERRO! Diferença de {diferenca:,.2f} sacas")
        print(f"   Percentual de erro: {(diferenca / 81834.82 * 100):.2f}%")
else:
    print("Real:        (não conseguiu calcular)")
