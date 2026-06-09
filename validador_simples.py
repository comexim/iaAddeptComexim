"""
VALIDADOR SIMPLES - 30 QUERIES COMPLEXAS
Calcula valores esperados para as perguntas do WhatsApp
"""
import pyodbc
from dotenv import load_dotenv
import os

load_dotenv()

# Conexão SQL
conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASSWORD')}"
)

def executar_query(procedure_name):
    """Executa uma stored procedure e retorna os resultados"""
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    query = f"SELECT * FROM dbo.{procedure_name}()"
    cursor.execute(query)
    results = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    results = [dict(zip(columns, row)) for row in results]
    cursor.close()
    conn.close()
    return results

print("="*100)
print("VALIDADOR AUTOMATICO - 30 QUERIES COMPLEXAS")
print("="*100)
print()

# ================================================================================================
# 1. IA_ESTOQUE
# ================================================================================================
print("\n" + "="*100)
print("1. IA_ESTOQUE")
print("="*100)

try:
    results = executar_query("IA_Estoque")
    print(f"\nTotal de registros no estoque: {len(results)}")

    print("\n[1.1] Temos mais cafe GRD brasileiro para exportacao ou LN2 europeu para consumo?")
    print("-"*100)
    grd_br_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                     for r in results
                     if r.get("linha") == "GRD"
                     and str(r.get("pais", "")).upper() == "BRASIL")
    ln2_eu_cons = sum(float(r.get("sacasConsumo", 0) or 0)
                      for r in results
                      if r.get("linha") == "LN2"
                      and str(r.get("pais", "")).upper() == "EUROPA")
    print(f"GRD brasileiro exportacao: {grd_br_exp:,.2f} sacas")
    print(f"LN2 europeu consumo: {ln2_eu_cons:,.2f} sacas")
    print(f"Maior: {'GRD brasileiro exportacao' if grd_br_exp > ln2_eu_cons else 'LN2 europeu consumo'}")

    print("\n[1.2] Qual certificacao tem mais sacas disponiveis para exportacao: Rainforest, 4C ou GC?")
    print("-"*100)
    rf_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                 for r in results
                 if "RF" in str(r.get("certificado", "")).upper())
    c4_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                 for r in results
                 if "4C" in str(r.get("certificado", "")).upper())
    gc_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                 for r in results
                 if "GC" in str(r.get("certificado", "")).upper())
    print(f"Rainforest exportacao: {rf_exp:,.2f} sacas")
    print(f"4C exportacao: {c4_exp:,.2f} sacas")
    print(f"GC exportacao: {gc_exp:,.2f} sacas")
    maior_cert = max([("Rainforest", rf_exp), ("4C", c4_exp), ("GC", gc_exp)], key=lambda x: x[1])
    print(f"Maior: {maior_cert[0]} ({maior_cert[1]:,.2f} sacas)")

    print("\n[1.3] Quanto cafe PVA brasileiro sem certificacao Rainforest temos para o mercado interno?")
    print("-"*100)
    pva_br_sem_rf_cons = sum(float(r.get("sacasConsumo", 0) or 0)
                             for r in results
                             if r.get("linha") == "PVA"
                             and str(r.get("pais", "")).upper() == "BRASIL"
                             and "RF" not in str(r.get("certificado", "")).upper())
    print(f"PVA brasileiro sem RF para consumo: {pva_br_sem_rf_cons:,.2f} sacas")

except Exception as e:
    print(f"ERRO ao consultar IA_Estoque: {e}")

# ================================================================================================
# 7. IA_SALDOBANCARIO
# ================================================================================================
print("\n\n" + "="*100)
print("7. IA_SALDOBANCARIO")
print("="*100)

try:
    results = executar_query("IA_SaldoBancario")

    print("\n[7.1] Tenho mais dinheiro no Itau Santos ou no Bradesco?")
    print("-"*100)
    itau = sum(float(r.get("saldo", 0) or 0)
               for r in results
               if "ITAU SANTOS" in str(r.get("banco", "")).upper())
    bradesco = sum(float(r.get("saldo", 0) or 0)
                   for r in results
                   if "BRADESCO" in str(r.get("banco", "")).upper())
    print(f"Itau Santos: R$ {itau:,.2f}")
    print(f"Bradesco: R$ {bradesco:,.2f}")
    print(f"Maior: {'Itau Santos' if itau > bradesco else 'Bradesco'}")

    print("\n[7.2] Quanto tenho em dolar em todos os bancos?")
    print("-"*100)
    dolar = sum(float(r.get("saldo", 0) or 0)
                for r in results
                if str(r.get("moeda", "")).upper() in ["USD", "DOLAR", "DOLARES"])
    print(f"Total em dolar: USD {dolar:,.2f}")

    print("\n[7.3] Quantos bancos estao com saldo negativo e qual o total devedor?")
    print("-"*100)
    negativos = [r for r in results if float(r.get("saldo", 0) or 0) < 0]
    total_devedor = sum(abs(float(r.get("saldo", 0) or 0)) for r in negativos)
    print(f"Bancos com saldo negativo: {len(negativos)}")
    print(f"Total devedor: R$ {total_devedor:,.2f}")

except Exception as e:
    print(f"ERRO ao consultar IA_SaldoBancario: {e}")

# ================================================================================================
# OUTRAS QUERIES - VALIDACAO MANUAL
# ================================================================================================
print("\n\n" + "="*100)
print("VALIDACAO MANUAL NECESSARIA PARA AS OUTRAS PERGUNTAS")
print("="*100)
print("""
Para as outras 24 perguntas, voce precisa:

1. Executar as queries SQL manualmente
2. Comparar com as respostas da IA

EXEMPLOS DE QUERIES:

--- VENDAS ---
[2.1] SELECT * FROM dbo.IA_Vendas(@mesEmbarque='202512')
      Filtre por cliente NESTLE vs STARBUCKS e compare totais

[2.2] SELECT * FROM dbo.IA_Vendas(@emissao='2026-01-23')  -- 7 dias atras
      Conte contratos unicos e some valores

--- COMPRAS ---
[3.1] SELECT * FROM dbo.IA_Compras(@emissao='2025-12-30')  -- 30 dias atras
      Agrupe por fornecedor e encontre o maior

[3.2] SELECT * FROM dbo.IA_Compras(@emissao='2025-11-01')
      SELECT * FROM dbo.IA_Compras(@emissao='2025-12-01')
      Compare totais

--- CONTAS PAGAS ---
[4.1] SELECT * FROM dbo.IA_ContasPagas(@emissao='2026-01-01')
      Filtre moeda='USD' e some

[4.2] SELECT * FROM dbo.IA_ContasPagas(@emissao='2026-01-23')  -- 7 dias atras
      Compare natureza 'CAFE' vs 'FRETE'

--- CONTAS A PAGAR ---
[5.1] SELECT * FROM dbo.IA_ContasAPagar()
      Filtre vencimento < '2026-01-30', agrupe por natureza 'CAFE'

[5.2] SELECT * FROM dbo.IA_ContasAPagar()
      Filtre vencimento entre '2026-01-30' e '2026-02-14'
      Filtre natureza 'INSS' ou 'SALARIO'

--- CONTAS A RECEBER ---
[6.1] SELECT * FROM dbo.IA_ContasAReceber()
      Filtre cliente='NESTLE' e vencimento entre hoje e +7 dias

[6.2] SELECT * FROM dbo.IA_ContasAReceber()
      Compare total NESTLE vs STARBUCKS

--- ORCAMENTO ---
[8.1] SELECT * FROM dbo.IA_Orcamento(@ano=2025, @mes='12')
      Compare orcado vs realizado

[8.2] SELECT * FROM dbo.IA_Orcamento(@ano=2025)
      Filtre meses 10,11,12, calcule (realizado/orcado)*100

--- COTACAO ---
[9.1] SELECT * FROM dbo.IA_Cotacao()
      Compare contratos C vs KC

[9.2] SELECT * FROM dbo.IA_Cotacao()
      Veja campo variacao para contrato C

--- DESPESAS DE VENDA ---
[10.1] SELECT * FROM dbo.IA_DespesaVenda()
       Agrupe por tipo, compare DESEMBARACO vs FUMIGACAO

[10.2] SELECT * FROM dbo.IA_DespesaVenda(@contrato='235/25')
       Some todas as despesas

""")

print("\n" + "="*100)
print("RESUMO")
print("="*100)
print("""
VALIDADAS AUTOMATICAMENTE:
- Perguntas 1.1, 1.2, 1.3 (Estoque)
- Perguntas 7.1, 7.2, 7.3 (Saldo Bancario)

VALIDACAO MANUAL:
- Perguntas 2.x a 6.x (Vendas, Compras, Contas)
- Perguntas 8.x a 10.x (Orcamento, Cotacao, Despesas)

Use as queries SQL acima como referencia!
""")

print("="*100)
