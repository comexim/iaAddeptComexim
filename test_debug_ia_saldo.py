"""
Debug: Simular exatamente o que a IA vê quando faz a consulta
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions

print("="*70)
print("DEBUG: Simulando consulta da IA")
print("="*70)

user = UserPermissions(
    telefone="11999999999",
    nome="Test User",
    email="test@test.com",
    direitos=["Financeiro", "Vendas", "Compras", "Orçamento"]
)

sql_tools = SQLTools(user)

# EXATAMENTE como a IA faria
sql_tools.user_query = "Quanto tenho no total entre Banco do Brasil e Itaú Santos somando todas as moedas (reais, dólares e euros)?"

print(f"\nPergunta do usuário:")
print(f"  {sql_tools.user_query}")

print("\n" + "-"*70)
print("Executando _pesquisa_saldo_bancario()...")
print("-"*70)

try:
    result = sql_tools._pesquisa_saldo_bancario()

    print("\n[OK] Consulta executada sem erros")
    print(f"\nTamanho do resultado: {len(result)} caracteres")

    # Salvar resultado completo
    with open("debug_ia_saldo_result.txt", "w", encoding="utf-8") as f:
        f.write(result)

    print("\n[OK] Resultado completo salvo em: debug_ia_saldo_result.txt")

    # Verificar se tem os bancos
    print("\n" + "="*70)
    print("VERIFICAÇÕES")
    print("="*70)

    checks = {
        "Filtro automático aplicado": "FILTRADO AUTOMATICAMENTE" in result,
        "BB presente": "BB STOS" in result or "BB NY" in result,
        "ITAU STOS presente": "ITAU STOS" in result,
        "Total de bancos <= 5": "Total de bancos únicos:" in result,
        "Aviso sobre múltiplos bancos": "MÚLTIPLOS BANCOS" in result,
        "Contém erro": "erro" in result.lower() or "desculpe" in result.lower()
    }

    for check_name, check_result in checks.items():
        status = "[OK]" if check_result else "[ERRO]"
        print(f"{status} {check_name}: {check_result}")

    # Extrair total de bancos
    import re
    match = re.search(r'Total de bancos únicos: (\d+)', result)
    if match:
        total_bancos = int(match.group(1))
        print(f"\n[INFO] Total de bancos retornados: {total_bancos}")

    # Mostrar primeiras 50 linhas do resultado
    print("\n" + "="*70)
    print("PRIMEIRAS 50 LINHAS DO RESULTADO (para a IA)")
    print("="*70)
    lines = result.split('\n')
    for i, line in enumerate(lines[:50], 1):
        print(f"{i:2}. {line}")

    if len(lines) > 50:
        print(f"\n... (mais {len(lines) - 50} linhas)")

except Exception as e:
    print(f"\n[ERRO] Exceção durante execução:")
    print(f"  Tipo: {type(e).__name__}")
    print(f"  Mensagem: {str(e)}")

    import traceback
    print("\nTraceback completo:")
    traceback.print_exc()
