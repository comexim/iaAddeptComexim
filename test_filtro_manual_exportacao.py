"""
Testa aplicação manual do filtro de exportação
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions
from app.core.database import sql_client
from dotenv import load_dotenv

load_dotenv()

# Criar usuário
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

print("=" * 80)
print("TESTE MANUAL: Filtro de sacas para exportação")
print("=" * 80)
print()

# Buscar dados direto do SQL
print("1. Buscando dados do SQL...")
results = sql_client.execute_function("dbo.IA_Estoque", None)
print(f"   Total de registros: {len(results)}")
print()

# Analisar distribuição
total_com_exportacao = 0
total_sem_exportacao = 0
total_sacas_antes = 0
total_sacas_export_antes = 0

for r in results:
    sacas = r.get("sacas", 0) or 0
    sacas_export = r.get("sacasExportacao", 0) or 0

    total_sacas_antes += sacas
    total_sacas_export_antes += sacas_export

    if sacas_export > 0:
        total_com_exportacao += 1
    else:
        total_sem_exportacao += 1

print(f"2. Análise dos registros:")
print(f"   - Total de registros: {len(results)}")
print(f"   - Com sacasExportacao > 0: {total_com_exportacao}")
print(f"   - Com sacasExportacao = 0: {total_sem_exportacao}")
print(f"   - Total de sacas (todas): {total_sacas_antes:,.2f}")
print(f"   - Total de sacasExportacao: {total_sacas_export_antes:,.2f}")
print()

# Aplicar filtro manualmente
print("3. Aplicando filtro manualmente...")
results_filtrados = [r for r in results if r.get("sacasExportacao", 0) > 0]
print(f"   Antes do filtro: {len(results)} registros")
print(f"   Depois do filtro: {len(results_filtrados)} registros")
print()

# Calcular totais após filtro
total_sacas_depois = sum(r.get("sacas", 0) or 0 for r in results_filtrados)
total_sacas_export_depois = sum(r.get("sacasExportacao", 0) or 0 for r in results_filtrados)
total_sacas_consumo_depois = sum(r.get("sacasConsumo", 0) or 0 for r in results_filtrados)

print(f"4. Totais APÓS filtro:")
print(f"   - Total de sacas: {total_sacas_depois:,.2f}")
print(f"   - Sacas exportação: {total_sacas_export_depois:,.2f}")
print(f"   - Sacas consumo: {total_sacas_consumo_depois:,.2f}")
print()

print("5. Comparação:")
print(f"   Teste 4 retornou: 127.031,72 sacas")
print(f"   Esperado após filtro: {total_sacas_depois:,.2f} sacas")
print()

if abs(127031.72 - total_sacas_antes) < 1:
    print("[CONCLUSÃO] O filtro NÃO foi aplicado no teste!")
    print("            Os resultados são SEM filtro (todos os registros)")
elif abs(total_sacas_depois - total_sacas_export_depois) < 1:
    print("[CONCLUSÃO] O filtro FOI aplicado mas há registros com sacasConsumo > 0 também!")
else:
    print("[CONCLUSÃO] Situação inesperada")
