"""
Testar o novo filtro automático para "embarcados"
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

# Simular a pergunta exata
pergunta = """Dos contratos de dezembro de 2025 que já foram embarcados,
quantos ainda não foram baixados no contas a receber?
Liste os 5 primeiros contratos e seus respectivos clientes."""

# Armazenar a pergunta (a IA faz isso)
sql_tools.user_query = pergunta

print("=" * 80)
print("TESTANDO FIX: Filtro automático para 'embarcados'")
print("=" * 80)
print()
print(f"Pergunta: {pergunta}")
print()
print("=" * 80)
print("CHAMANDO _pesquisa_vendas com periodo='dezembro 2025'")
print("=" * 80)
print()

# A IA provavelmente chamou assim:
resultado = sql_tools._pesquisa_vendas(periodo="dezembro 2025")

# Salvar resultado em arquivo
with open("resultado_fix_embarcados.txt", "w", encoding="utf-8") as f:
    f.write(resultado)

# Contar quantos contratos estão na resposta
import re
contratos_match = re.findall(r'(\d+/\d+[A-Z]?)', resultado)

print()
print("=" * 80)
print("RESULTADO:")
print("=" * 80)
print(f"Tamanho da resposta: {len(resultado)} caracteres")
print(f"Salvo em: resultado_fix_embarcados.txt")
print()
print("=" * 80)
print("ANÁLISE:")
print("=" * 80)
print(f"Contratos encontrados na resposta: {len(set(contratos_match))}")
print(f"Primeiros 10 contratos únicos: {sorted(set(contratos_match))[:10]}")
print()

# Verificar se o filtro foi aplicado
if "embarcados (com saidaNavio)" in resultado or "[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'" in resultado:
    print("✓ Filtro automático 'embarcados' foi APLICADO")
else:
    print("✗ Filtro automático 'embarcados' NÃO foi aplicado")

# Procurar no início do resultado quantos registros
total_match = re.search(r'Total de registros SQL: (\d+)', resultado)
if total_match:
    total_registros = int(total_match.group(1))
    print(f"Total de registros retornados: {total_registros}")
    print()
    if total_registros == 16:
        print("✓✓✓ SUCESSO! Retornou 16 contratos (esperado)")
    elif total_registros == 60:
        print("✗✗✗ ERRO! Retornou 60 contratos (todos os de dez/2025, sem filtrar embarcados)")
    else:
        print(f"? Retornou {total_registros} contratos (verificar se está correto)")
