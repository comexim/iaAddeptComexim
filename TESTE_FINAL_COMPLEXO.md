# 🎯 TESTE FINAL - 30 PERGUNTAS COMPLEXAS

## Instruções
- 3 perguntas complexas para cada stored procedure
- Teste via WhatsApp e anote as respostas
- Valide cada resposta contra o banco de dados
- Marque ✅ (correto) ou ❌ (incorreto)

---

## 1️⃣ IA_Estoque (Estoque)

### Pergunta 1.1 - Filtros múltiplos + comparação
```
Temos mais café GRD brasileiro para exportação ou LN2 europeu para consumo?
```
**Testa**: Múltiplos filtros (tipo + país + destino) + query comparativa

**Esperado**:
- GRD brasileiro exportação: ______ sacas
- LN2 europeu consumo: ______ sacas
- Resposta: Temos mais ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 1.2 - Certificação + destino + ranking
```
Qual certificação tem mais sacas disponíveis para exportação: Rainforest, 4C ou GC?
```
**Testa**: Agregação por certificação + filtro de exportação + comparação

**Esperado**:
- Rainforest exportação: ______ sacas
- 4C exportação: ______ sacas
- GC exportação: ______ sacas
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 1.3 - Combinação complexa
```
Quanto café PVA brasileiro sem certificação Rainforest temos para o mercado interno?
```
**Testa**: Múltiplos filtros (tipo + país + exclusão de certificação + destino)

**Esperado**: ______ sacas

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 2️⃣ IA_Vendas (Vendas e Embarques)

### Pergunta 2.1 - Período + cliente + comparação
```
Vendi mais para a Nestlé ou para a Starbucks em dezembro de 2025?
```
**Testa**: Filtro de período + múltiplos clientes + comparação

**Esperado**:
- Nestlé dez/25: ______ sacas (ou R$ ______)
- Starbucks dez/25: ______ sacas (ou R$ ______)
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 2.2 - Data relativa + agregação
```
Quantos contratos embarcaram na última semana e qual foi o valor total?
```
**Testa**: Data natural relativa + contagem + soma de valores

**Esperado**:
- Contratos: ______ contratos
- Valor total: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 2.3 - Status específico
```
Quanto em valor está baixado no contas a receber em janeiro de 2026?
```
**Testa**: Filtro de campo específico (baixados_jan2026) + soma de valores

**Esperado**: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 3️⃣ IA_Compras (Compras e Aquisições)

### Pergunta 3.1 - Período + ranking
```
Qual foi o maior fornecedor de café nos últimos 30 dias?
```
**Testa**: Data relativa + agregação por fornecedor + ranking

**Esperado**:
- Fornecedor: ______
- Quantidade: ______ sacas (ou R$ ______)

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 3.2 - Comparação de períodos
```
Comprei mais café em novembro ou dezembro de 2025?
```
**Testa**: Múltiplos períodos + comparação + agregação

**Esperado**:
- Novembro/25: ______ sacas
- Dezembro/25: ______ sacas
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 3.3 - Data específica + total
```
Quanto gastei com compras de café no dia 15 de dezembro de 2025?
```
**Testa**: Data específica (dia) + soma de valores

**Esperado**: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 4️⃣ IA_ContasPagas (Contas Pagas)

### Pergunta 4.1 - Período + fornecedor + moeda
```
Quanto paguei em dólar para fornecedores este mês?
```
**Testa**: Período relativo + filtro de moeda + agregação

**Esperado**: USD ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 4.2 - Centro de custo + comparação
```
Gastei mais com café ou com frete nos últimos 7 dias?
```
**Testa**: Filtro por natureza/centro de custo + comparação

**Esperado**:
- Café: R$ ______
- Frete: R$ ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 4.3 - Banco + período
```
Quantos pagamentos fiz pelo Itaú Santos em dezembro de 2025 e qual o total?
```
**Testa**: Filtro de banco + período + contagem + soma

**Esperado**:
- Quantidade: ______ pagamentos
- Total: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 5️⃣ IA_ContasAPagar (Contas a Pagar)

### Pergunta 5.1 - Status + urgência
```
Quanto em contas vencidas tenho a pagar e quantas são para fornecedores de café?
```
**Testa**: Filtro de vencimento + natureza específica + múltiplas agregações

**Esperado**:
- Total vencido: R$ ______
- Total café vencido: R$ ______
- Quantidade títulos café: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 5.2 - Período futuro + natureza
```
Quanto vou pagar de INSS e salários nos próximos 15 dias?
```
**Testa**: Data futura relativa + múltiplas naturezas + soma

**Esperado**:
- INSS: R$ ______
- Salários: R$ ______
- Total: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 5.3 - Comparação de tipos
```
Tenho mais a pagar em compra de café ou tarifas bancárias este mês?
```
**Testa**: Filtro de natureza + período + comparação

**Esperado**:
- Compra de café: R$ ______
- Tarifas bancárias: R$ ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 6️⃣ IA_ContasAReceber (Contas a Receber)

### Pergunta 6.1 - Cliente + urgência
```
Quanto a Nestlé vai me pagar nos próximos 7 dias?
```
**Testa**: Filtro de cliente + período futuro + soma

**Esperado**: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 6.2 - Comparação de clientes
```
Quem me deve mais: Nestlé ou Starbucks?
```
**Testa**: Query comparativa + múltiplos clientes + agregação

**Esperado**:
- Nestlé: R$ ______
- Starbucks: R$ ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 6.3 - Período + status
```
Quantos títulos vencidos tenho a receber e qual o valor total?
```
**Testa**: Filtro de vencimento + contagem + soma

**Esperado**:
- Títulos vencidos: ______
- Valor total: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 7️⃣ IA_SaldoBancario (Saldo Bancário)

### Pergunta 7.1 - Múltiplos bancos + comparação
```
Tenho mais dinheiro no Itaú Santos ou no Bradesco?
```
**Testa**: Query comparativa + filtro de bancos + agregação

**Esperado**:
- Itaú Santos: R$ ______
- Bradesco: R$ ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 7.2 - Moeda + total
```
Quanto tenho em dólar em todos os bancos?
```
**Testa**: Filtro de moeda + agregação total

**Esperado**: USD ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 7.3 - Análise de saldo
```
Quantos bancos estão com saldo negativo e qual o total devedor?
```
**Testa**: Filtro por sinal + contagem + soma (valor absoluto)

**Esperado**:
- Bancos negativos: ______
- Total devedor: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 8️⃣ IA_Orcamento (Orçamento vs Realizado)

### Pergunta 8.1 - Período + comparação
```
Vendi mais ou menos que o orçado em dezembro de 2025?
```
**Testa**: Período específico + comparação orçado vs realizado

**Esperado**:
- Orçado: R$ ______
- Realizado: R$ ______
- Status: ______ (acima/abaixo)
- Diferença: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 8.2 - Trimestre + percentual
```
Qual foi o percentual de realização do orçamento no último trimestre de 2025?
```
**Testa**: Período trimestral + cálculo de percentual

**Esperado**:
- Orçado: R$ ______
- Realizado: R$ ______
- Percentual: ______%

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 8.3 - Ranking de meses
```
Em qual mês de 2025 tive o maior estouro de orçamento?
```
**Testa**: Múltiplos períodos + cálculo de diferença + ranking

**Esperado**:
- Mês: ______
- Orçado: R$ ______
- Realizado: R$ ______
- Estouro: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 9️⃣ IA_Cotacao (Cotação da Bolsa)

### Pergunta 9.1 - Contrato + comparação
```
Qual está mais caro: contrato C (Arábica) ou KC (Robusta)?
```
**Testa**: Múltiplos contratos + comparação de preços

**Esperado**:
- Contrato C: USD ______
- Contrato KC: USD ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 9.2 - Variação
```
Quanto subiu ou caiu o contrato C hoje?
```
**Testa**: Cálculo de variação + análise de tendência

**Esperado**:
- Variação: ______ cents/lb
- Percentual: ______%
- Tendência: ______ (subiu/caiu)

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 9.3 - Análise completa
```
Qual o spread entre o preço de abertura e fechamento do KC?
```
**Testa**: Múltiplos campos + cálculo de diferença

**Esperado**:
- Abertura: USD ______
- Fechamento: USD ______
- Spread: USD ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 🔟 IA_DespesaVenda (Despesas de Venda)

### Pergunta 10.1 - Tipo + comparação
```
Gastei mais com desembaraço ou fumigação em todos os contratos?
```
**Testa**: Query comparativa + agregação por tipo + soma total

**Esperado**:
- Desembaraço: R$ ______
- Fumigação: R$ ______
- Maior: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 10.2 - Contrato específico + total
```
Quanto gastei no total com despesas do contrato 235/25?
```
**Testa**: Filtro de contrato + soma de todas as despesas

**Esperado**: R$ ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

### Pergunta 10.3 - Ranking + agregação
```
Qual tipo de despesa teve mais ocorrências em 2025 e quantos contratos foram afetados?
```
**Testa**: Agregação complexa + contagem + ranking

**Esperado**:
- Tipo: ______
- Ocorrências: ______
- Contratos: ______

**Resultado IA**:


**Validação**: ⬜ Correto ⬜ Incorreto


---

## 📊 RESUMO DOS TESTES

### Distribuição por Complexidade

**Filtros Simples**: ____/30
**Filtros Múltiplos**: ____/30
**Queries Comparativas**: ____/30
**Agregações Complexas**: ____/30
**Datas Naturais**: ____/30
**Rankings**: ____/30

### Taxa de Acerto Geral

```
Total de perguntas: 30
Corretas: ____
Incorretas: ____
Taxa de acerto: ____%
```

### Análise de Erros

**Erros por categoria**:
- [ ] Filtros automáticos incorretos
- [ ] Comparações erradas
- [ ] Agregações incorretas
- [ ] Parse de data natural
- [ ] Outros: ___________

---

## ✅ CRITÉRIO DE APROVAÇÃO

- **Mínimo aceitável**: 27/30 (90%)
- **Excelente**: 29/30 (96.7%)
- **Perfeito**: 30/30 (100%)

**Status Final**: ⬜ Aprovado ⬜ Necessita ajustes

---

## 📝 OBSERVAÇÕES

Anote aqui qualquer comportamento interessante, erro específico ou sugestão de melhoria:

```
[Espaço para observações]
```

---

**Data do teste**: __________
**Testador**: __________
**Versão do sistema**: __________
