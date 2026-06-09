# 🎯 GUIA SIMPLES - COMO VALIDAR AS 30 PERGUNTAS

## 📱 Passo 1: Testar no WhatsApp

1. Abra o arquivo `30_PERGUNTAS_WHATSAPP.txt`
2. Copie cada pergunta (1.1 até 10.3)
3. Cole no WhatsApp e envie
4. **Anote a resposta completa da IA** em um arquivo ou bloco de notas

---

## 🔍 Passo 2: Validar as Respostas

### ✅ VALIDAÇÃO AUTOMÁTICA (6 perguntas - Estoque e Saldo Bancário)

**No servidor Linux**, execute:

```bash
cd /opt/agente-comexim-whatsapp
python3 << 'EOF'
import pyodbc
import os
from dotenv import load_dotenv

load_dotenv()

conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.getenv('SQL_SERVER')};"
    f"DATABASE={os.getenv('SQL_DATABASE')};"
    f"UID={os.getenv('SQL_USER')};"
    f"PWD={os.getenv('SQL_PASSWORD')}"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# [1.1] GRD brasileiro exportação vs LN2 europeu consumo
cursor.execute("SELECT * FROM dbo.IA_Estoque()")
results = cursor.fetchall()
columns = [column[0] for column in cursor.description]
results = [dict(zip(columns, row)) for row in results]

grd_br_exp = sum(float(r.get("sacasExportacao", 0) or 0)
                 for r in results
                 if r.get("linha") == "GRD"
                 and str(r.get("pais", "")).upper() == "BRASIL")

ln2_eu_cons = sum(float(r.get("sacasConsumo", 0) or 0)
                  for r in results
                  if r.get("linha") == "LN2"
                  and str(r.get("pais", "")).upper() == "EUROPA")

print("[1.1] GRD brasileiro exportacao vs LN2 europeu consumo:")
print(f"  GRD BR exportacao: {grd_br_exp:,.2f} sacas")
print(f"  LN2 EU consumo: {ln2_eu_cons:,.2f} sacas")
print(f"  Maior: {'GRD brasileiro' if grd_br_exp > ln2_eu_cons else 'LN2 europeu'}")

# [1.2] Certificações para exportação
rf_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "RF" in str(r.get("certificado", "")).upper())
c4_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "4C" in str(r.get("certificado", "")).upper())
gc_exp = sum(float(r.get("sacasExportacao", 0) or 0)
             for r in results
             if "GC" in str(r.get("certificado", "")).upper())

print("\n[1.2] Certificacoes para exportacao:")
print(f"  Rainforest: {rf_exp:,.2f} sacas")
print(f"  4C: {c4_exp:,.2f} sacas")
print(f"  GC: {gc_exp:,.2f} sacas")
maior = max([("Rainforest", rf_exp), ("4C", c4_exp), ("GC", gc_exp)], key=lambda x: x[1])
print(f"  Maior: {maior[0]}")

# [1.3] PVA brasileiro sem RF para consumo
pva_br_sem_rf = sum(float(r.get("sacasConsumo", 0) or 0)
                    for r in results
                    if r.get("linha") == "PVA"
                    and str(r.get("pais", "")).upper() == "BRASIL"
                    and "RF" not in str(r.get("certificado", "")).upper())

print(f"\n[1.3] PVA brasileiro sem RF para consumo: {pva_br_sem_rf:,.2f} sacas")

cursor.close()
conn.close()
EOF
```

---

### 📋 VALIDAÇÃO MANUAL (24 perguntas restantes)

Para as outras perguntas, você precisa **executar queries SQL e comparar manualmente**.

#### 🔧 Como fazer:

1. **Conecte no SQL Server** (usando Azure Data Studio, SSMS, ou qualquer cliente SQL)
2. **Execute as queries abaixo** para cada pergunta
3. **Compare** o resultado SQL com a resposta da IA
4. **Marque** ✅ se igual ou ❌ se diferente

---

## 📊 QUERIES SQL PARA CADA PERGUNTA

### 2️⃣ VENDAS

**[2.1] Vendi mais para a Nestlé ou Starbucks em dezembro de 2025?**
```sql
SELECT cliente, SUM(sacas60kg) as total_sacas, SUM(valorTotal) as valor_total
FROM dbo.IA_Vendas(@mesEmbarque='202512')
WHERE cliente IN ('NESTLE', 'STARBUCKS')
GROUP BY cliente
ORDER BY total_sacas DESC
```

**[2.2] Quantos contratos embarcaram na última semana?**
```sql
-- Ajuste a data para 7 dias atrás
SELECT COUNT(DISTINCT numeroContrato) as total_contratos,
       SUM(valorTotal) as valor_total
FROM dbo.IA_Vendas(@emissao='2026-01-23')
```

**[2.3] Quanto em valor está baixado no contas a receber em jan/2026?**
```sql
SELECT * FROM dbo.IA_Vendas()
-- Procure por campos como "baixado_jan2026" ou "contratos_baixados_jan2026"
-- Some os valores desse campo
```

---

### 3️⃣ COMPRAS

**[3.1] Qual foi o maior fornecedor nos últimos 30 dias?**
```sql
SELECT fornecedor, SUM(quantidade) as total_sacas, SUM(valor) as valor_total
FROM dbo.IA_Compras(@emissao='2025-12-30')  -- 30 dias atrás
GROUP BY fornecedor
ORDER BY total_sacas DESC
```

**[3.2] Comprei mais café em novembro ou dezembro de 2025?**
```sql
-- Novembro
SELECT SUM(quantidade) as total FROM dbo.IA_Compras(@emissao='2025-11-01')

-- Dezembro
SELECT SUM(quantidade) as total FROM dbo.IA_Compras(@emissao='2025-12-01')
```

**[3.3] Quanto gastei com compras no dia 15/12/2025?**
```sql
SELECT SUM(valor) as total
FROM dbo.IA_Compras(@emissao='2025-12-15')
```

---

### 4️⃣ CONTAS PAGAS

**[4.1] Quanto paguei em dólar este mês?**
```sql
SELECT SUM(valor) as total_usd
FROM dbo.IA_ContasPagas(@emissao='2026-01-01')
WHERE moeda = 'USD'
```

**[4.2] Gastei mais com café ou frete nos últimos 7 dias?**
```sql
SELECT
  SUM(CASE WHEN natureza LIKE '%CAFE%' THEN valor ELSE 0 END) as cafe,
  SUM(CASE WHEN natureza LIKE '%FRETE%' THEN valor ELSE 0 END) as frete
FROM dbo.IA_ContasPagas(@emissao='2026-01-23')  -- 7 dias atrás
```

**[4.3] Quantos pagamentos fiz pelo Itaú Santos em dez/2025?**
```sql
SELECT COUNT(*) as quantidade, SUM(valor) as total
FROM dbo.IA_ContasPagas(@emissao='2025-12-01')
WHERE banco LIKE '%ITAU SANTOS%'
```

---

### 5️⃣ CONTAS A PAGAR

**[5.1] Quanto em contas vencidas tenho a pagar? Quantas são de café?**
```sql
SELECT
  SUM(valor) as total_vencido,
  SUM(CASE WHEN natureza LIKE '%CAFE%' THEN valor ELSE 0 END) as total_cafe,
  COUNT(CASE WHEN natureza LIKE '%CAFE%' THEN 1 END) as qtd_titulos_cafe
FROM dbo.IA_ContasAPagar()
WHERE vencimento < '2026-01-30'  -- hoje
```

**[5.2] Quanto vou pagar de INSS e salários nos próximos 15 dias?**
```sql
SELECT
  SUM(CASE WHEN natureza LIKE '%INSS%' THEN valor ELSE 0 END) as inss,
  SUM(CASE WHEN natureza LIKE '%SALARIO%' THEN valor ELSE 0 END) as salarios,
  SUM(valor) as total
FROM dbo.IA_ContasAPagar()
WHERE vencimento BETWEEN '2026-01-30' AND '2026-02-14'
  AND (natureza LIKE '%INSS%' OR natureza LIKE '%SALARIO%')
```

**[5.3] Tenho mais a pagar em compra de café ou tarifas bancárias este mês?**
```sql
SELECT
  SUM(CASE WHEN natureza LIKE '%CAFE%' THEN valor ELSE 0 END) as cafe,
  SUM(CASE WHEN natureza LIKE '%TARIFA%' THEN valor ELSE 0 END) as tarifas
FROM dbo.IA_ContasAPagar()
WHERE vencimento LIKE '202601%'  -- janeiro 2026
```

---

### 6️⃣ CONTAS A RECEBER

**[6.1] Quanto a Nestlé vai me pagar nos próximos 7 dias?**
```sql
SELECT SUM(valor) as total
FROM dbo.IA_ContasAReceber()
WHERE cliente LIKE '%NESTLE%'
  AND vencimento BETWEEN '2026-01-30' AND '2026-02-06'
```

**[6.2] Quem me deve mais: Nestlé ou Starbucks?**
```sql
SELECT
  SUM(CASE WHEN cliente LIKE '%NESTLE%' THEN valor ELSE 0 END) as nestle,
  SUM(CASE WHEN cliente LIKE '%STARBUCKS%' THEN valor ELSE 0 END) as starbucks
FROM dbo.IA_ContasAReceber()
```

**[6.3] Quantos títulos vencidos tenho a receber e qual o valor total?**
```sql
SELECT COUNT(*) as titulos, SUM(valor) as total
FROM dbo.IA_ContasAReceber()
WHERE vencimento < '2026-01-30'
```

---

### 7️⃣ SALDO BANCÁRIO

**[7.1] Tenho mais dinheiro no Itaú Santos ou Bradesco?**
```sql
SELECT
  SUM(CASE WHEN banco LIKE '%ITAU SANTOS%' THEN saldo ELSE 0 END) as itau,
  SUM(CASE WHEN banco LIKE '%BRADESCO%' THEN saldo ELSE 0 END) as bradesco
FROM dbo.IA_SaldoBancario()
```

**[7.2] Quanto tenho em dólar em todos os bancos?**
```sql
SELECT SUM(saldo) as total_usd
FROM dbo.IA_SaldoBancario()
WHERE moeda IN ('USD', 'DOLAR', 'DOLARES')
```

**[7.3] Quantos bancos estão com saldo negativo e qual o total devedor?**
```sql
SELECT COUNT(*) as bancos_negativos, SUM(ABS(saldo)) as total_devedor
FROM dbo.IA_SaldoBancario()
WHERE saldo < 0
```

---

### 8️⃣ ORÇAMENTO

**[8.1] Vendi mais ou menos que o orçado em dezembro de 2025?**
```sql
SELECT orcado, realizado, (realizado - orcado) as diferenca
FROM dbo.IA_Orcamento(@ano=2025, @mes='12')
```

**[8.2] Qual foi o percentual de realização no último trimestre de 2025?**
```sql
SELECT
  SUM(orcado) as orcado,
  SUM(realizado) as realizado,
  (SUM(realizado) * 100.0 / SUM(orcado)) as percentual
FROM dbo.IA_Orcamento(@ano=2025)
WHERE mes IN ('10', '11', '12')
```

**[8.3] Em qual mês de 2025 tive o maior estouro de orçamento?**
```sql
SELECT mes, orcado, realizado, (realizado - orcado) as estouro
FROM dbo.IA_Orcamento(@ano=2025)
ORDER BY (realizado - orcado) DESC
```

---

### 9️⃣ COTAÇÃO

**[9.1] Qual está mais caro: contrato C (Arábica) ou KC (Robusta)?**
```sql
SELECT contrato, ultimo
FROM dbo.IA_Cotacao()
WHERE contrato IN ('C', 'KC')
```

**[9.2] Quanto subiu ou caiu o contrato C hoje?**
```sql
SELECT contrato, variacao, ultimo
FROM dbo.IA_Cotacao()
WHERE contrato = 'C'
```

**[9.3] Qual o spread entre abertura e fechamento do KC?**
```sql
SELECT contrato, abertura, fechamento, (fechamento - abertura) as spread
FROM dbo.IA_Cotacao()
WHERE contrato = 'KC'
```

---

### 🔟 DESPESAS DE VENDA

**[10.1] Gastei mais com desembaraço ou fumigação?**
```sql
SELECT
  SUM(CASE WHEN tipo LIKE '%DESEMBARA%' THEN despesaReal ELSE 0 END) as desembaraco,
  SUM(CASE WHEN tipo LIKE '%FUMIGA%' THEN despesaReal ELSE 0 END) as fumigacao
FROM dbo.IA_DespesaVenda()
```

**[10.2] Quanto gastei no total com despesas do contrato 235/25?**
```sql
SELECT SUM(despesaReal) as total
FROM dbo.IA_DespesaVenda(@contrato='235/25')
```

**[10.3] Qual tipo de despesa teve mais ocorrências em 2025?**
```sql
SELECT tipo, COUNT(*) as ocorrencias, COUNT(DISTINCT contrato) as contratos
FROM dbo.IA_DespesaVenda()
GROUP BY tipo
ORDER BY ocorrencias DESC
```

---

## ✅ CHECKLIST DE VALIDAÇÃO

```
ESTOQUE:
[ ] 1.1 - GRD brasileiro exportação vs LN2 europeu consumo
[ ] 1.2 - Certificação com mais sacas para exportação
[ ] 1.3 - PVA brasileiro sem RF para consumo

VENDAS:
[ ] 2.1 - Nestlé vs Starbucks em dez/2025
[ ] 2.2 - Contratos embarcados na última semana
[ ] 2.3 - Valor baixado em jan/2026

COMPRAS:
[ ] 3.1 - Maior fornecedor nos últimos 30 dias
[ ] 3.2 - Novembro vs dezembro de 2025
[ ] 3.3 - Gastos em 15/12/2025

CONTAS PAGAS:
[ ] 4.1 - Pago em dólar este mês
[ ] 4.2 - Café vs frete nos últimos 7 dias
[ ] 4.3 - Pagamentos pelo Itaú em dez/2025

CONTAS A PAGAR:
[ ] 5.1 - Contas vencidas (total e café)
[ ] 5.2 - INSS e salários próximos 15 dias
[ ] 5.3 - Café vs tarifas este mês

CONTAS A RECEBER:
[ ] 6.1 - Nestlé próximos 7 dias
[ ] 6.2 - Nestlé vs Starbucks (total)
[ ] 6.3 - Títulos vencidos (quantidade e valor)

SALDO BANCÁRIO:
[ ] 7.1 - Itaú Santos vs Bradesco
[ ] 7.2 - Total em dólar
[ ] 7.3 - Bancos negativos

ORÇAMENTO:
[ ] 8.1 - Acima ou abaixo em dez/2025
[ ] 8.2 - Percentual último trimestre 2025
[ ] 8.3 - Mês com maior estouro

COTAÇÃO:
[ ] 9.1 - C vs KC (mais caro)
[ ] 9.2 - Variação do contrato C
[ ] 9.3 - Spread abertura-fechamento KC

DESPESAS:
[ ] 10.1 - Desembaraço vs fumigação
[ ] 10.2 - Total despesas contrato 235/25
[ ] 10.3 - Tipo com mais ocorrências
```

---

## 🎯 META DE SUCESSO

**Mínimo**: 27/30 corretas (90%)
**Excelente**: 29/30 (96.7%)
**Perfeito**: 30/30 (100%)

Boa sorte! 🚀
