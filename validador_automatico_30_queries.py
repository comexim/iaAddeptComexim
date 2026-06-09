"""
VALIDADOR AUTOMÁTICO - 30 QUERIES COMPLEXAS
Ajuda a validar as respostas da IA comparando com o banco de dados
"""
import pyodbc
from dotenv import load_dotenv
import os
from decimal import Decimal
import json

load_dotenv()

# Conexão SQL
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASSWORD')}"
)

def executar_query(procedure_name, filters=None):
    """Executa uma stored procedure e retorna os resultados"""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    if filters:
        # Monta chamada com filtros
        filter_str = ", ".join([f"@{k}='{v}'" for k, v in filters.items()])
        query = f"SELECT * FROM dbo.{procedure_name}({filter_str})"
    else:
        query = f"SELECT * FROM dbo.{procedure_name}()"

    cursor.execute(query)
    results = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in results]

    cursor.close()
    conn.close()

    return results

def formatar_valor(valor):
    """Formata valores para exibição"""
    if isinstance(valor, (Decimal, float)):
        return f"{float(valor):,.2f}"
    return str(valor)

print("=" * 100)
print("VALIDADOR AUTOMÁTICO - 30 QUERIES COMPLEXAS")
print("=" * 100)
print()
print("Este script ajuda a validar as respostas da IA contra o banco de dados.")
print("Para cada pergunta, execute manualmente no WhatsApp e compare com os valores calculados aqui.")
print()
print("=" * 100)
print()

# ================================================================================================
# 1. IA_ESTOQUE
# ================================================================================================
print("📦 1. IA_ESTOQUE")
print("=" * 100)

print("\n[1.1] Temos mais café GRD brasileiro para exportação ou LN2 europeu para consumo?")
print("-" * 100)
results = executar_query("IA_Estoque")
grd_br_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                 for r in results
                 if r.get("linha") == "GRD"
                 and str(r.get("pais", "")).upper() == "BRASIL")
ln2_eu_cons = sum(float(r.get("sacasConsumo", 0) or 0)
                  for r in results
                  if r.get("linha") == "LN2"
                  and str(r.get("pais", "")).upper() == "EUROPA")
print(f"GRD brasileiro exportação: {grd_br_exp:,.2f} sacas")
print(f"LN2 europeu consumo: {ln2_eu_cons:,.2f} sacas")
print(f"Maior: {'GRD brasileiro exportação' if grd_br_exp > ln2_eu_cons else 'LN2 europeu consumo'}")

print("\n[1.2] Qual certificação tem mais sacas disponíveis para exportação: Rainforest, 4C ou GC?")
print("-" * 100)
rf_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "RF" in str(r.get("certificado", "")).upper())
c4_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "4C" in str(r.get("certificado", "")).upper())
gc_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "GC" in str(r.get("certificado", "")).upper())
print(f"Rainforest exportação: {rf_exp:,.2f} sacas")
print(f"4C exportação: {c4_exp:,.2f} sacas")
print(f"GC exportação: {gc_exp:,.2f} sacas")
maior_cert = max([("Rainforest", rf_exp), ("4C", c4_exp), ("GC", gc_exp)], key=lambda x: x[1])
print(f"Maior: {maior_cert[0]} ({maior_cert[1]:,.2f} sacas)")

print("\n[1.3] Quanto café PVA brasileiro sem certificação Rainforest temos para o mercado interno?")
print("-" * 100)
pva_br_sem_rf_cons = sum(float(r.get("sacasConsumo", 0) or 0)
                         for r in results
                         if r.get("linha") == "PVA"
                         and str(r.get("pais", "")).upper() == "BRASIL"
                         and "RF" not in str(r.get("certificado", "")).upper())
print(f"PVA brasileiro sem RF para consumo: {pva_br_sem_rf_cons:,.2f} sacas")

# ================================================================================================
# 2. IA_VENDAS
# ================================================================================================
print("\n\n" + "=" * 100)
print("📈 2. IA_VENDAS")
print("=" * 100)

print("\n[2.1] Vendi mais para a Nestlé ou para a Starbucks em dezembro de 2025?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Vendas(@mesEmbarque='202512')")
print("Filtre por cliente e compare os valores/sacas totais")

print("\n[2.2] Quantos contratos embarcaram na última semana e qual foi o valor total?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Vendas(@emissao='YYYY-MM-DD') -- data de 7 dias atrás")
print("Conte os contratos únicos e some os valores")

print("\n[2.3] Quanto em valor está baixado no contas a receber em janeiro de 2026?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Vendas()")
print("Verifique campo 'contratos_baixados_jan2026' ou similar")

# ================================================================================================
# 3. IA_COMPRAS
# ================================================================================================
print("\n\n" + "=" * 100)
print("🛒 3. IA_COMPRAS")
print("=" * 100)

print("\n[3.1] Qual foi o maior fornecedor de café nos últimos 30 dias?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Compras(@emissao='YYYY-MM-DD') -- 30 dias atrás")
print("Agrupe por fornecedor e encontre o maior")

print("\n[3.2] Comprei mais café em novembro ou dezembro de 2025?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute duas queries e compare:")
print("SELECT * FROM dbo.IA_Compras(@emissao='2025-11-01')")
print("SELECT * FROM dbo.IA_Compras(@emissao='2025-12-01')")

print("\n[3.3] Quanto gastei com compras de café no dia 15 de dezembro de 2025?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Compras(@emissao='2025-12-15')")
print("Some os valores totais")

# ================================================================================================
# 4. IA_CONTASPAGAS
# ================================================================================================
print("\n\n" + "=" * 100)
print("💳 4. IA_CONTASPAGAS")
print("=" * 100)

print("\n[4.1] Quanto paguei em dólar para fornecedores este mês?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasPagas(@emissao='2026-01-01')")
print("Filtre moeda='USD' e some os valores")

print("\n[4.2] Gastei mais com café ou com frete nos últimos 7 dias?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasPagas(@emissao='YYYY-MM-DD')")
print("Filtre por natureza contendo 'CAFE' vs 'FRETE' e compare totais")

print("\n[4.3] Quantos pagamentos fiz pelo Itaú Santos em dezembro de 2025 e qual o total?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasPagas(@emissao='2025-12-01')")
print("Filtre banco='ITAU SANTOS', conte registros e some valores")

# ================================================================================================
# 5. IA_CONTASAPAGAR
# ================================================================================================
print("\n\n" + "=" * 100)
print("📋 5. IA_CONTASAPAGAR")
print("=" * 100)

print("\n[5.1] Quanto em contas vencidas tenho a pagar e quantas são para fornecedores de café?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAPagar()")
print("Filtre vencimento < HOJE, some total e filtre natureza contendo 'CAFE'")

print("\n[5.2] Quanto vou pagar de INSS e salários nos próximos 15 dias?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAPagar()")
print("Filtre vencimento entre HOJE e +15 dias, natureza contendo 'INSS' ou 'SALARIO'")

print("\n[5.3] Tenho mais a pagar em compra de café ou tarifas bancárias este mês?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAPagar()")
print("Filtre vencimento em jan/2026, compare natureza 'CAFE' vs 'TARIFA'")

# ================================================================================================
# 6. IA_CONTASARECEBER
# ================================================================================================
print("\n\n" + "=" * 100)
print("💰 6. IA_CONTASARECEBER")
print("=" * 100)

print("\n[6.1] Quanto a Nestlé vai me pagar nos próximos 7 dias?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAReceber()")
print("Filtre cliente='NESTLE' e vencimento entre HOJE e +7 dias")

print("\n[6.2] Quem me deve mais: Nestlé ou Starbucks?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAReceber()")
print("Compare soma total de cliente='NESTLE' vs cliente='STARBUCKS'")

print("\n[6.3] Quantos títulos vencidos tenho a receber e qual o valor total?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_ContasAReceber()")
print("Filtre vencimento < HOJE, conte e some valores")

# ================================================================================================
# 7. IA_SALDOBANCARIO
# ================================================================================================
print("\n\n" + "=" * 100)
print("🏦 7. IA_SALDOBANCARIO")
print("=" * 100)

print("\n[7.1] Tenho mais dinheiro no Itaú Santos ou no Bradesco?")
print("-" * 100)
try:
    results = executar_query("IA_SaldoBancario")
    itau = sum(float(r.get("saldo", 0) or 0)
               for r in results
               if "ITAU SANTOS" in str(r.get("banco", "")).upper())
    bradesco = sum(float(r.get("saldo", 0) or 0)
                   for r in results
                   if "BRADESCO" in str(r.get("banco", "")).upper())
    print(f"Itaú Santos: R$ {itau:,.2f}")
    print(f"Bradesco: R$ {bradesco:,.2f}")
    print(f"Maior: {'Itaú Santos' if itau > bradesco else 'Bradesco'}")
except Exception as e:
    print(f"⚠️ Erro ao consultar: {e}")
    print("Execute manualmente: SELECT * FROM dbo.IA_SaldoBancario()")

print("\n[7.2] Quanto tenho em dólar em todos os bancos?")
print("-" * 100)
try:
    results = executar_query("IA_SaldoBancario")
    dolar = sum(float(r.get("saldo", 0) or 0)
                for r in results
                if str(r.get("moeda", "")).upper() in ["USD", "DOLAR", "DOLARES"])
    print(f"Total em dólar: USD {dolar:,.2f}")
except Exception as e:
    print(f"⚠️ Erro ao consultar: {e}")

print("\n[7.3] Quantos bancos estão com saldo negativo e qual o total devedor?")
print("-" * 100)
try:
    results = executar_query("IA_SaldoBancario")
    negativos = [r for r in results if float(r.get("saldo", 0) or 0) < 0]
    total_devedor = sum(abs(float(r.get("saldo", 0) or 0)) for r in negativos)
    print(f"Bancos com saldo negativo: {len(negativos)}")
    print(f"Total devedor: R$ {total_devedor:,.2f}")
except Exception as e:
    print(f"⚠️ Erro ao consultar: {e}")

# ================================================================================================
# 8. IA_ORCAMENTO
# ================================================================================================
print("\n\n" + "=" * 100)
print("📊 8. IA_ORCAMENTO")
print("=" * 100)

print("\n[8.1] Vendi mais ou menos que o orçado em dezembro de 2025?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Orcamento(@ano=2025, @mes='12')")
print("Compare campos 'orcado' vs 'realizado'")

print("\n[8.2] Qual foi o percentual de realização do orçamento no último trimestre de 2025?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Orcamento(@ano=2025, @mes=['10','11','12'])")
print("Some orcado e realizado, calcule percentual: (realizado/orcado)*100")

print("\n[8.3] Em qual mês de 2025 tive o maior estouro de orçamento?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Orcamento(@ano=2025)")
print("Para cada mês, calcule (realizado - orcado) e encontre o maior")

# ================================================================================================
# 9. IA_COTACAO
# ================================================================================================
print("\n\n" + "=" * 100)
print("📈 9. IA_COTACAO")
print("=" * 100)

print("\n[9.1] Qual está mais caro: contrato C (Arábica) ou KC (Robusta)?")
print("-" * 100)
try:
    results = executar_query("IA_Cotacao")
    c_contract = next((r for r in results if r.get("contrato") == "C"), None)
    kc_contract = next((r for r in results if r.get("contrato") == "KC"), None)
    if c_contract and kc_contract:
        print(f"Contrato C: {c_contract.get('ultimo', 'N/A')} cents/lb")
        print(f"Contrato KC: {kc_contract.get('ultimo', 'N/A')} cents/lb")
    else:
        print("⚠️ Contratos não encontrados")
except Exception as e:
    print(f"⚠️ Erro ao consultar: {e}")

print("\n[9.2] Quanto subiu ou caiu o contrato C hoje?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Cotacao()")
print("Verifique campo 'variacao' ou calcule (ultimo - anterior)")

print("\n[9.3] Qual o spread entre o preço de abertura e fechamento do KC?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_Cotacao()")
print("Calcule (fechamento - abertura) para contrato KC")

# ================================================================================================
# 10. IA_DESPESAVENDA
# ================================================================================================
print("\n\n" + "=" * 100)
print("💸 10. IA_DESPESAVENDA")
print("=" * 100)

print("\n[10.1] Gastei mais com desembaraço ou fumigação em todos os contratos?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_DespesaVenda()")
print("Filtre tipo contendo 'DESEMBARAÇO' vs 'FUMIGAÇÃO' e compare totais")

print("\n[10.2] Quanto gastei no total com despesas do contrato 235/25?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_DespesaVenda(@contrato='235/25')")
print("Some todas as despesas (campo 'despesaReal')")

print("\n[10.3] Qual tipo de despesa teve mais ocorrências em 2025 e quantos contratos foram afetados?")
print("-" * 100)
print("⚠️ VALIDAÇÃO MANUAL NECESSÁRIA")
print("Execute: SELECT * FROM dbo.IA_DespesaVenda()")
print("Agrupe por tipo, conte ocorrências e contratos distintos")

print("\n\n" + "=" * 100)
print("✅ VALIDAÇÃO CONCLUÍDA")
print("=" * 100)
print()
print("Use os valores acima para comparar com as respostas da IA no WhatsApp.")
print("Para queries marcadas como 'VALIDAÇÃO MANUAL NECESSÁRIA', execute as SQLs sugeridas.")
print()
print("=" * 100)
