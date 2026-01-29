# Análise: Resposta da IA sobre Contratos Não Embarcados sem BL

## Data: 2026-01-29

## Pergunta do Usuário
```
Quantos contratos não foram embarcados e não têm BL?
Período: janeiro de 2026
```

## Resposta da IA
```
Em janeiro de 2026, há 18 contratos que não foram embarcados e não possuem BL.
Aqui estão os 5 primeiros contratos:
1. 036/25 (BIJDENDIJK)
2. 011/26 (INTERAMERICAN COFFE)
3. 012/26 (INTERAMERICAN COFFE)
4. 589/25 (ATLANTIC USA IN)
5. 080/25B (F&J COMERCIO DE CAFE)
```

## Dados Reais (Validação no Banco)

### Total Correto: 15 contratos

### Contratos NÃO Embarcados sem BL (15 contratos):
1. 001/26 - NEUMANN GRUPPE USA I - 1,357.54 sacas
2. 001/26 - BERNHARD ROTHFOS GMB - 731.69 sacas
3. 034/25 - AHOLD COFFEE - 700.00 sacas
4. 036/25 - BIJDENDIJK - 324.23 sacas ✅
5. 080/25B - F&J COMERCIO DE CAFE - 508.47 sacas ✅
6. 080/25F - F&J COMERCIO DE CAFE - 254.23 sacas
7. 081/25B - COFFEA IMPORTACAO, E - 864.40 sacas
8. 082/25A - COFFEA IMPORTACAO, E - 762.71 sacas
9. 082/25B - COFFEA IMPORTACAO, E - 1,677.96 sacas
10. 086/25B - J R COMERCIO E EXPOR - 369.15 sacas
11. 086/25C - J R COMERCIO E EXPOR - 369.15 sacas
12. 086/25D - J R COMERCIO E EXPOR - 369.15 sacas
13. 087/25 - FINLAY BEVERAGES - 1,146.20 sacas
14. 589/25 - ATLANTIC USA IN - 2,290.67 sacas ✅
15. 592/25 - FINLAY BEVERAGES - 1,320.90 sacas

### Contratos EMBARCADOS sem BL (19 contratos):
Inclui:
- **011/26 - INTERAMERICAN COFFE** - Saída: 20260129 ❌ (IA listou como NÃO embarcado!)
- **012/26 - INTERAMERICAN COFFE** - Saída: 20260203 ❌ (IA listou como NÃO embarcado!)
- 003/26 - VOLCAFE - Saída: 20260203
- 019/26 - LOS CINCO HISPANOS S - Saída: 20260130
- ... (mais 15 contratos)

## Análise dos Erros

### ❌ Erro 1: NÚMERO INCORRETO
- **IA disse**: 18 contratos
- **Valor correto**: 15 contratos
- **Diferença**: 3 contratos a mais (20% de erro)

### ❌ Erro 2: CONTRATOS EMBARCADOS INCLUÍDOS
A IA incluiu na lista de "NÃO embarcados":
- **011/26** (INTERAMERICAN COFFE) - TEM saidaNavio: 20260129
- **012/26** (INTERAMERICAN COFFE) - TEM saidaNavio: 20260203

**Estes contratos ESTÃO EMBARCADOS!** Não deveriam aparecer na resposta!

### ✅ Acertos Parciais
A IA acertou 3 dos 5 contratos listados:
- ✅ 036/25 (BIJDENDIJK) - CORRETO (não embarcado, sem BL)
- ❌ 011/26 (INTERAMERICAN COFFE) - ERRADO (embarcado!)
- ❌ 012/26 (INTERAMERICAN COFFE) - ERRADO (embarcado!)
- ✅ 589/25 (ATLANTIC USA IN) - CORRETO (não embarcado, sem BL)
- ✅ 080/25B (F&J COMERCIO DE CAFE) - CORRETO (não embarcado, sem BL)

**Taxa de acerto**: 3/5 = 60%

## Resposta Correta Esperada

```
Em janeiro de 2026, há 15 contratos que não foram embarcados e não possuem BL.
Aqui estão os 5 primeiros contratos:
1. 001/26 (NEUMANN GRUPPE USA I)
2. 001/26 (BERNHARD ROTHFOS GMB)
3. 034/25 (AHOLD COFFEE)
4. 036/25 (BIJDENDIJK)
5. 080/25B (F&J COMERCIO DE CAFE)
```

## Possíveis Causas

### 1. Fix não foi aplicado no servidor
- Commit 9550b55 pode não ter sido deployado ainda
- Precisa verificar se git pull foi executado
- Precisa verificar se serviço foi reiniciado

### 2. Cache não foi limpo
- Bytecode Python pode estar em cache
- Precisa executar: `find . -type d -name __pycache__ -exec rm -rf {} +`

### 3. Filtros não estão sendo aplicados
- Filtro "não embarcados" pode não estar detectando o padrão
- Filtro "sem BL" pode não estar sendo aplicado corretamente
- Necessário verificar logs do servidor

## Próximos Passos

1. ✅ Verificar se commit foi deployado: `git log --oneline -1`
2. ✅ Verificar se serviço foi reiniciado: `systemctl status agente-comexim`
3. ✅ Limpar cache: `find . -type d -name __pycache__ -exec rm -rf {} +`
4. ✅ Verificar logs: `journalctl -u agente-comexim --since "5 minutes ago"`
5. ✅ Verificar se filtros foram aplicados nos logs

## Status

🔴 **PROBLEMA CONFIRMADO - FIX NÃO ESTÁ FUNCIONANDO NO SERVIDOR**

A resposta ainda está incorreta:
- Número errado (18 vs 15)
- Contratos embarcados sendo incluídos (011/26, 012/26)
- Mix de contratos corretos e incorretos
