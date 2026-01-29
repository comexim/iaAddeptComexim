# Mapeamento Completo: IA_Estoque()

## Data do Mapeamento
2026-01-29

## Resumo Executivo

A função **IA_Estoque()** retorna informações detalhadas sobre o estoque de café da empresa, incluindo:
- Localização (filial, armazém)
- Identificação do lote
- Classificação do café (linha, certificado)
- Métricas de qualidade (impureza, quebra, PVA, grinder, peneiras)
- Quantidades (peso, sacas total, sacas consumo, sacas exportação)
- Origem (país)

## Estrutura de Dados

### Total de Colunas: 18
### Registros Analisados: 100

---

## 1. CAMPOS DE IDENTIFICAÇÃO E LOCALIZAÇÃO

### 1.1 filial
- **Tipo**: string
- **Descrição**: Nome da filial onde o estoque está localizado
- **Exemplo**: "OURO FINO"
- **Valores únicos (amostra)**:
  - OURO FINO: 100 registros
- **Observação**: Na amostra de 100 registros, todos são da filial OURO FINO

### 1.2 armazem
- **Tipo**: string
- **Descrição**: Nome do armazém onde o café está estocado
- **Exemplo**: "ARMAZEM OURO FINO"
- **Observação**: Campo relacionado à filial

### 1.3 pais
- **Tipo**: string
- **Descrição**: País de origem do café
- **Exemplo**: "BRASIL"
- **Observação**: Campo importante para rastreabilidade

---

## 2. CAMPOS DE IDENTIFICAÇÃO DO LOTE

### 2.1 lote
- **Tipo**: string
- **Descrição**: Código identificador único do lote de café
- **Exemplo**: "TR-06043100"
- **Observação**: Campo chave para identificação

### 2.2 loteFonecedor
- **Tipo**: string
- **Descrição**: Código do lote fornecido pelo fornecedor
- **Exemplo**: "" (pode estar vazio)
- **Observação**: Campo opcional, nem sempre preenchido

---

## 3. CAMPOS DE CLASSIFICAÇÃO DO CAFÉ

### 3.1 linha
- **Tipo**: string
- **Descrição**: Linha de produto/tipo de café
- **Exemplo**: "PVA"
- **Valores únicos (amostra de 100)**:
  - PVA: 36 registros
  - GRD: 43 registros
  - LN1: 6 registros
  - LN2/3: 6 registros
  - LN3: 3 registros
  - LN1/2: 2 registros
  - LN2: 2 registros
  - CD: 1 registro
  - FUNDI: 1 registro
- **Observação**: 9 tipos diferentes identificados

### 3.2 certificado
- **Tipo**: string
- **Descrição**: Tipo de certificação do café
- **Exemplo**: "RF"
- **Valores únicos (amostra de 100)**:
  - RF: 69 registros (maioria)
  - 4C: 8 registros
  - GC: 6 registros
  - CP: 2 registros
  - GT: 2 registros
- **Observação**: RF (Rainforest?) é a certificação mais comum

---

## 4. CAMPOS DE MÉTRICAS DE QUALIDADE (percentuais)

### 4.1 impureza
- **Tipo**: float
- **Descrição**: Percentual de impureza no café
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 0.35%
  - Máximo: 100.00%
  - Média: 18.88%
  - Registros não-zero: 48/100
- **Observação**: Valores menores indicam melhor qualidade

### 4.2 quebra
- **Tipo**: float
- **Descrição**: Percentual de grãos quebrados
- **Exemplo**: 0.0
- **Observação**: Campo sempre 0.0 na amostra analisada

### 4.3 pva
- **Tipo**: float
- **Descrição**: Percentual PVA (provavelmente "Peneira Acima")
- **Exemplo**: 100.0
- **Estatísticas**:
  - Mínimo: 1.00%
  - Máximo: 100.00%
  - Média: 56.69%
  - Registros não-zero: 64/100
- **Observação**: Relacionado à classificação por peneira

### 4.4 grinder
- **Tipo**: float
- **Descrição**: Percentual de café tipo grinder
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 2.00%
  - Máximo: 100.00%
  - Média: 68.08%
  - Registros não-zero: 50/100

### 4.5 peneiraGrauda
- **Tipo**: float
- **Descrição**: Percentual retido em peneira graúda (grãos grandes)
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 4.73%
  - Máximo: 100.00%
  - Média: 68.66%
  - Registros não-zero: 14/100

### 4.6 peneiraMTGB
- **Tipo**: float
- **Descrição**: Percentual retido em peneira MTGB (Miúdo, Tipo Grão Bom?)
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 4.99%
  - Máximo: 100.00%
  - Média: 69.45%
  - Registros não-zero: 15/100

### 4.7 fundo
- **Tipo**: float
- **Descrição**: Percentual de fundo (resíduos/grãos pequenos demais)
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 0.09%
  - Máximo: 19.00%
  - Média: 7.29%
  - Registros não-zero: 8/100

---

## 5. CAMPOS DE QUANTIDADE

### 5.1 peso
- **Tipo**: float
- **Descrição**: Peso do lote em quilogramas
- **Exemplo**: 1056.8
- **Estatísticas**:
  - Mínimo: 115.70 kg
  - Máximo: 57.559,40 kg
  - Média: 6.963,43 kg
  - Registros não-zero: 100/100
- **Observação**: Todos os registros têm peso

### 5.2 sacas
- **Tipo**: Decimal
- **Descrição**: Total de sacas de café no estoque
- **Exemplo**: 17.91
- **Estatísticas**:
  - Mínimo: 1.96 sacas
  - Máximo: 975.58 sacas
  - Média: 118.02 sacas
  - Registros não-zero: 100/100
- **Observação**: Campo principal para contagem de estoque

### 5.3 sacasConsumo
- **Tipo**: Decimal
- **Descrição**: Sacas destinadas ao consumo interno/mercado interno
- **Exemplo**: 17.91
- **Estatísticas**:
  - Mínimo: 0.46 sacas
  - Máximo: 734.86 sacas
  - Média: 62.51 sacas
  - Registros não-zero: 80/100
- **Observação**: 80% dos registros têm sacas para consumo

### 5.4 sacasExportacao
- **Tipo**: Decimal
- **Descrição**: Sacas destinadas à exportação
- **Exemplo**: 0.0
- **Estatísticas**:
  - Mínimo: 1.96 sacas
  - Máximo: 565.83 sacas
  - Média: 106.27 sacas
  - Registros não-zero: 64/100
- **Observação**: 64% dos registros têm sacas para exportação

---

## 6. RELAÇÕES ENTRE CAMPOS

### 6.1 Equação de Sacas
```
sacas = sacasConsumo + sacasExportacao
```

### 6.2 Conversão Peso/Sacas
- 1 saca de café ≈ 60 kg
- peso (kg) ≈ sacas × 60

---

## 7. EXEMPLOS DE REGISTROS COMPLETOS

### Exemplo 1: Café PVA Rainforest para Consumo
```
filial: OURO FINO
lote: TR-06043100
linha: PVA
certificado: RF
peso: 1.056,8 kg
sacas: 17.91
sacasConsumo: 17.91
sacasExportacao: 0.0
armazem: ARMAZEM OURO FINO
pais: BRASIL
```

### Exemplo 2: Café PVA Rainforest para Consumo
```
filial: OURO FINO
lote: TR-06043000
linha: PVA
certificado: RF
peso: 671,2 kg
sacas: 11.37
sacasConsumo: 11.37
sacasExportacao: 0.0
armazem: ARMAZEM OURO FINO
pais: BRASIL
```

### Exemplo 3: Café PVA Rainforest para Consumo
```
filial: OURO FINO
lote: RB-064904NN
linha: PVA
certificado: RF
peso: 1.133,6 kg
sacas: 19.21
sacasConsumo: 19.21
sacasExportacao: 0.0
armazem: ARMAZEM OURO FINO
pais: BRASIL
```

---

## 8. CAMPOS CHAVE PARA QUERIES

### Para Localização:
- **filial**: Filtrar por localização
- **armazem**: Filtrar por armazém específico

### Para Identificação:
- **lote**: Buscar lote específico

### Para Classificação:
- **linha**: Filtrar por tipo de café (PVA, GRD, LN1, etc.)
- **certificado**: Filtrar por certificação (RF, 4C, GC, etc.)

### Para Quantidades:
- **sacas**: Total em estoque
- **sacasConsumo**: Disponível para consumo
- **sacasExportacao**: Disponível para exportação
- **peso**: Quantidade em quilogramas

### Para Qualidade:
- **impureza**: Nível de impureza
- **pva**: Classificação PVA
- **grinder**: Tipo grinder
- **peneiraGrauda**, **peneiraMTGB**, **fundo**: Classificação por peneira

---

## 9. QUERIES COMUNS ESPERADAS

### 9.1 Consultas de Quantidade
- "Quantas sacas temos em estoque?"
- "Qual o estoque total?"
- "Quantas sacas para exportação?"
- "Quantas sacas para consumo?"

### 9.2 Consultas por Localização
- "Quanto café temos em Ouro Fino?"
- "Qual o estoque do armazém X?"

### 9.3 Consultas por Tipo
- "Quanto café PVA temos?"
- "Quantas sacas de GRD?"
- "Estoque de café linha LN1?"

### 9.4 Consultas por Certificação
- "Quanto café Rainforest temos?" (RF)
- "Estoque de café 4C?"

### 9.5 Consultas por Qualidade
- "Café com menos de 10% de impureza"
- "Lotes PVA acima de 80%"

### 9.6 Consultas Combinadas
- "Quantas sacas de café PVA com certificação RF para exportação?"
- "Estoque de GRD em Ouro Fino disponível para consumo?"

---

## 10. OBSERVAÇÕES IMPORTANTES

### 10.1 Dados da Amostra
- Amostra de 100 registros (TOP 100)
- Todos da filial OURO FINO
- Todos do país BRASIL

### 10.2 Campos Opcionais
- **loteFonecedor**: Pode estar vazio
- **sacasConsumo**: 20% dos registros têm valor 0
- **sacasExportacao**: 36% dos registros têm valor 0

### 10.3 Integridade de Dados
- Campo **peso** sempre preenchido
- Campo **sacas** sempre preenchido
- Equação: sacas = sacasConsumo + sacasExportacao deve ser respeitada

---

## 11. VALIDAÇÃO

Script utilizado: `test_mapeamento_estoque.py`

```bash
python test_mapeamento_estoque.py
```

Resultado:
- [OK] 18 colunas identificadas
- [OK] 100 registros analisados
- [OK] Tipos de dados mapeados
- [OK] Valores únicos extraídos
- [OK] Estatísticas calculadas
- [OK] Exemplos documentados

---

## 12. ARQUIVOS GERADOS

1. **test_mapeamento_estoque.py** - Script de mapeamento
2. **mapeamento_estoque.txt** - Saída detalhada do script
3. **MAPEAMENTO_IA_ESTOQUE.md** - Esta documentação

---

## Status

[OK] MAPEAMENTO COMPLETO E VALIDADO

Data: 2026-01-29
