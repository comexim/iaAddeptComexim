"""
Testa implementação de queries sobre estoque com filtros e agregações automáticas
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
    direitos=["Vendas", "Estoque"],
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

# Lista de queries para testar
queries = [
    {
        "query": "Quantas sacas temos em estoque?",
        "descricao": "Query simples - total de sacas",
        "esperado": "Deve retornar total agregado de sacas"
    },
    {
        "query": "Quanto café PVA temos?",
        "descricao": "Filtro por linha PVA",
        "esperado": "Deve filtrar apenas registros com linha=PVA"
    },
    {
        "query": "Quanto café Rainforest temos?",
        "descricao": "Filtro por certificado Rainforest (RF)",
        "esperado": "Deve filtrar apenas registros com certificado=RF"
    },
    {
        "query": "Quantas sacas para exportação?",
        "descricao": "Filtro por sacasExportacao > 0",
        "esperado": "Deve filtrar apenas registros com sacasExportacao > 0"
    },
    {
        "query": "Quanto café GRD temos?",
        "descricao": "Filtro por linha GRD",
        "esperado": "Deve filtrar apenas registros com linha=GRD"
    },
    {
        "query": "Sacas para consumo em estoque",
        "descricao": "Filtro por sacasConsumo > 0",
        "esperado": "Deve filtrar apenas registros com sacasConsumo > 0"
    },
]

print("=" * 80)
print("TESTE DE QUERIES SOBRE ESTOQUE")
print("=" * 80)
print()

for i, teste in enumerate(queries, 1):
    print(f"\n{'=' * 80}")
    print(f"TESTE {i}/{len(queries)}: {teste['descricao']}")
    print(f"{'=' * 80}")
    print()
    print(f"Query: \"{teste['query']}\"")
    print(f"Esperado: {teste['esperado']}")
    print()
    print("-" * 80)
    print("EXECUTANDO...")
    print("-" * 80)
    print()

    # Configurar query
    sql_tools.user_query = teste['query']
    sql_tools.user_query_original = teste['query']

    try:
        # Chamar a tool
        resultado = sql_tools._pesquisa_estoque()

        # Salvar resultado em arquivo
        filename = f"resultado_estoque_{i}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Query: {teste['query']}\n")
            f.write(f"Descrição: {teste['descricao']}\n")
            f.write(f"Esperado: {teste['esperado']}\n")
            f.write("=" * 80 + "\n\n")
            f.write(resultado)

        print(f"[OK] Resultado salvo em: {filename}")
        print(f"[INFO] Tamanho: {len(resultado)} caracteres")
        print()

        # Análise rápida do resultado
        if "AGREGADOS" in resultado:
            print("[INFO] Resultado foi AGREGADO (muitos registros)")

            # Extrair totais
            if "Total de Sacas:" in resultado:
                import re
                match = re.search(r'Total de Sacas:\s+([\d,.]+)\s+sacas', resultado)
                if match:
                    total = match.group(1)
                    print(f"       Total de Sacas: {total}")

            # Contar grupos
            if "linha" in resultado.lower():
                print(f"       Agregado por: LINHA")
            elif "certificado" in resultado.lower():
                print(f"       Agregado por: CERTIFICADO")

        elif "Total de registros:" in resultado:
            # Extrair número de registros
            import re
            match = re.search(r'Total de registros:\s+(\d+)', resultado)
            if match:
                total_reg = match.group(1)
                print(f"[INFO] Resultado NÃO agregado ({total_reg} registros)")

        # Verificar se filtros foram aplicados
        if "[FILTRO AUTOMÁTICO]" in resultado:
            print("[OK] Filtros automáticos foram aplicados")

            # Extrair quais filtros
            import re
            filtros = re.findall(r'\[FILTRO AUTOMÁTICO\] Aplicado filtro \'([^\']+)\'', resultado)
            for filtro in filtros:
                print(f"     - {filtro}")
        else:
            print("[INFO] Nenhum filtro automático aplicado")

        print()

    except Exception as e:
        print(f"[ERRO] Falha ao executar query: {e}")
        import traceback
        traceback.print_exc()
        print()

print("=" * 80)
print("RESUMO DOS TESTES")
print("=" * 80)
print()
print(f"Total de queries testadas: {len(queries)}")
print()
print("Arquivos gerados:")
for i in range(1, len(queries) + 1):
    print(f"  - resultado_estoque_{i}.txt")
print()
print("=" * 80)
print("[OK] TESTES CONCLUIDOS!")
print("=" * 80)
print()
print("Próximos passos:")
print("1. Revisar os arquivos resultado_estoque_*.txt")
print("2. Verificar se filtros foram aplicados corretamente")
print("3. Verificar se agregações estão corretas")
print("4. Se tudo OK, fazer deploy para o servidor")
