"""
Testar FIX: Filtro para contratos NÃO embarcados sem BL
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
print("TESTE: Fix de filtro para 'NÃO embarcados sem BL'")
print("=" * 80)
print()

# Query original (para filtros)
query_original = "Quantos contratos não foram embarcados e não têm BL?"
sql_tools.user_query = query_original
sql_tools.user_query_original = query_original

print(f"Query: '{query_original}'")
print(f"Período: janeiro de 2026")
print()
print(f"[DEBUG] user_query: '{sql_tools.user_query}'")
print(f"[DEBUG] user_query_original: '{sql_tools.user_query_original}'")
print()
print("=" * 80)
print("EXECUTANDO TOOL...")
print("=" * 80)
print()

# Chamar a tool
resultado = sql_tools._pesquisa_vendas(periodo="janeiro de 2026")

# Salvar resultado
with open("resultado_fix_nao_embarcados_bl.txt", "w", encoding="utf-8") as f:
    f.write(resultado)

print(f"Resultado salvo em: resultado_fix_nao_embarcados_bl.txt")
print(f"Tamanho: {len(resultado)} caracteres")
print()

# Verificar se o filtro foi aplicado
print("=" * 80)
print("VERIFICAÇÃO DO FIX:")
print("=" * 80)
print()

if "[FILTRO AUTOMÁTICO] Aplicado filtro 'não embarcados'" in resultado:
    print("[OK] Filtro de 'não embarcados' FOI APLICADO")
else:
    print("[X] Filtro de 'não embarcados' NÃO foi aplicado")

if "[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'" in resultado:
    print("[ERRO] Filtro de 'embarcados' foi aplicado INCORRETAMENTE!")
else:
    print("[OK] Filtro de 'embarcados' NÃO foi aplicado (correto)")

print()

# Verificar se menciona "RESPOSTA DIRETA"
if "RESPOSTA DIRETA" in resultado:
    print("[OK] Encontrou 'RESPOSTA DIRETA' - otimização especial aplicada")

    # Extrair o número de contratos
    import re
    match = re.search(r'(\d+)\s+(?:ainda\s+)?não\s+t[eê]m\s+(?:número\s+de\s+)?bl', resultado.lower())
    if match:
        numero = int(match.group(1))
        print(f"     Número extraído: {numero} contratos")

        if numero == 15:
            print("     [SUCESSO] Valor CORRETO! (esperado: 15)")
        else:
            print(f"     [ERRO] Valor INCORRETO! (esperado: 15, obtido: {numero})")
    else:
        print("     [X] Não conseguiu extrair número da resposta")
else:
    # Tentar contar manualmente
    print("[INFO] Não encontrou 'RESPOSTA DIRETA' - contando manualmente...")

    # Contar contratos no resultado
    import re
    contratos = re.findall(r'"contrato":\s*"([^"]+)"', resultado)
    if contratos:
        print(f"[INFO] Encontrados {len(contratos)} contratos no resultado")

        if len(contratos) == 15:
            print("     [SUCESSO] Quantidade CORRETA! (esperado: 15)")
        else:
            print(f"     [ERRO] Quantidade INCORRETA! (esperado: 15, obtido: {len(contratos)})")

        print()
        print("     Primeiros 5 contratos:")
        for i, c in enumerate(contratos[:5], 1):
            print(f"        {i}. {c}")
    else:
        print("[X] Não conseguiu contar contratos")

print()
print("=" * 80)
print("ANÁLISE DO LOG:")
print("=" * 80)
print()

# Procurar linhas de log no resultado
log_lines = [line for line in resultado.split('\n') if 'FILTRO AUTOMÁTICO' in line or 'Total de registros' in line]
for line in log_lines:
    print(f"  {line}")

print()
print("=" * 80)
print("RESULTADO FINAL:")
print("=" * 80)
print()

# Verificar se o fix funcionou
sucesso = (
    "[FILTRO AUTOMÁTICO] Aplicado filtro 'não embarcados'" in resultado and
    "[FILTRO AUTOMÁTICO] Aplicado filtro 'embarcados'" not in resultado
)

if sucesso:
    print("[SUCESSO] FIX FUNCIONOU!")
    print("  - Filtro 'não embarcados' aplicado")
    print("  - Filtro 'embarcados' NÃO aplicado")
    print("  - Esperado: 15 contratos não embarcados sem BL")
else:
    print("[ERRO] FIX NÃO FUNCIONOU!")
    print("  Verifique o arquivo resultado_fix_nao_embarcados_bl.txt")
