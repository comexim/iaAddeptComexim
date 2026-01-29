# Deploy do Fix: Embarcados + Baixados Dezembro 2025

## Problema Corrigido

A IA estava respondendo "**Não foram encontrados contratos**" quando perguntado sobre contratos de dezembro 2025 embarcados e não baixados, mas **59 contratos** existiam.

### Causas Raiz Identificadas

**Causa 1**: Extração falsa de cliente
- Query: "contratos que ainda **não foram baixados**"
- Bug: `_extract_client_name()` extraía "não foram baixados" como nome de cliente
- Resultado: Filtrava por cliente inexistente → 0 contratos

**Causa 2**: Otimização hardcoded para janeiro 2026
- Linhas 289-336 de sql_tools.py tinham otimização que **sempre** usava janeiro 2026
- Ativada quando query mencionava "embarcados" **E** "baixados" simultaneamente
- Resultado: Query sobre dezembro 2025 retornava dados de janeiro 2026

## Soluções Implementadas

### Fix 1: Proteção contra falsos positivos de cliente
**Arquivo**: [app/agents/sql_tools.py](app/agents/sql_tools.py#L43-L73)

Adicionadas 9 proteções contra extração de frases operacionais como nomes de cliente:
```python
palavras_operacao = [
    r'\bnão\s+foram\s+baixad',      # "não foram baixados"
    r'\bforam\s+baixad',            # "foram baixados"
    r'\bja\s+foram\s+baixad',       # "já foram baixados"
    r'\bforam\s+embarcad',          # "foram embarcados"
    r'\bforam\s+pagos',             # "foram pagos"
    r'\bforam\s+quitad',            # "foram quitados"
    r'\bainda\s+não',               # "ainda não"
    r'\bsem\s+bl',                  # "sem bl"
    r'\bsem\s+valor\s+fixado',      # "sem valor fixado"
]
```

### Fix 2: Desabilitar otimização hardcoded
**Arquivo**: [app/agents/sql_tools.py](app/agents/sql_tools.py#L292)

Alterado de:
```python
if self.user_query and re.search(r'embarc(ad[oa]s?|aram|ou|am).*baix(ad[oa]s?|aram|ou|am)|...', self.user_query.lower()):
```

Para:
```python
if False and self.user_query and re.search(...):
    # DESABILITADA: estava hardcoded para janeiro 2026 e causando bugs em outras datas
```

## Validação do Fix

✅ **ANTES DO FIX**:
```
Pergunta: "Dos contratos de dezembro de 2025 que já foram embarcados,
          quantos ainda não foram baixados no contas a receber?"

Resposta: "Nenhum contrato encontrado para o cliente 'não foram baixados'"
```

✅ **DEPOIS DO FIX**:
```
Resultado: 60 contratos encontrados (54.373 caracteres de dados)
Primeiros 5:
  1. 382/25 - THE DRIP CO.LTD
  2. 397/25 - MIORI
  3. 406/25 - MIORI
  4. 443/25 - H A BENNETT
  5. 457/25 - H A BENNETT
```

## Deploy no Servidor

### 📋 Passo a passo:

```bash
# 1. Conectar no servidor
ssh root@srv824573

# 2. Navegar para o diretório
cd /opt/agente-comexim-whatsapp

# 3. Verificar branch atual e status
git branch --show-current
git status

# 4. Puxar alterações do GitHub
git pull

# 5. Verificar se o fix 1 está presente (proteção contra falsos clientes)
echo "=== Verificando FIX 1: Proteção contra falsos positivos ==="
grep -A 3 "NÃO tenta extrair cliente se a query menciona operações" app/agents/sql_tools.py

# Deve retornar algo como:
#   # NÃO tenta extrair cliente se a query menciona operações financeiras/logísticas
#   # que podem ser confundidas com nomes (ex: "não foram baixados", "foram embarcados")
#   palavras_operacao = [

# 6. Verificar se o fix 2 está presente (desabilitar otimização hardcoded)
echo "=== Verificando FIX 2: Desabilitar otimização janeiro 2026 ==="
grep -B 2 "if False and self.user_query" app/agents/sql_tools.py | head -n 5

# Deve retornar algo como:
#   # DESABILITADA: estava hardcoded para janeiro 2026 e causando bugs em outras datas
#   # TODO: Reimplementar de forma dinâmica se necessário
#   if False and self.user_query and re.search(r'embarc...

# 7. Limpar cache do Python (IMPORTANTE!)
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 8. Reiniciar o serviço
systemctl restart agente-comexim

# 9. Aguardar inicialização
sleep 10

# 10. Verificar status
systemctl status agente-comexim

# 11. Verificar logs recentes
journalctl -u agente-comexim -n 30 --no-pager
```

## Verificação Pós-Deploy

Fazer a pergunta no WhatsApp:
```
Dos contratos de dezembro de 2025 que já foram embarcados,
quantos ainda não foram baixados no contas a receber?
Liste os 5 primeiros contratos e seus respectivos clientes.
```

**Resposta esperada**:
```
Foram encontrados aproximadamente 59 contratos de dezembro de 2025
que já foram embarcados mas ainda não foram baixados no contas a receber.

Os 5 primeiros contratos são:

1. *382/25* - THE DRIP CO.LTD
2. *397/25* - MIORI
3. *406/25* - MIORI
4. *443/25* - H A BENNETT
5. *457/25* - H A BENNETT

[Mais detalhes...]
```

## Commit

- **Hash**: 4379b0b
- **Mensagem**: "Fix CRÍTICO: corrigir bug em queries sobre embarcados+baixados"
- **Arquivo**: app/agents/sql_tools.py
  - Linhas 43-73: Proteção contra extração de frases operacionais
  - Linha 292: Desabilitar otimização hardcoded janeiro 2026

## Troubleshooting

### Se o serviço não iniciar:
```bash
# Ver erro completo
journalctl -u agente-comexim -n 50 --no-pager

# Verificar sintaxe Python
python3 -m py_compile app/agents/sql_tools.py
```

### Se ainda retornar "Não foram encontrados":
```bash
# Verificar se os caches foram limpos
find . -name "*.pyc" -o -name "__pycache__"

# Deve retornar vazio após limpeza
```

### Se retornar dados de janeiro 2026 ao invés de dezembro 2025:
```bash
# Verificar se a otimização foi desabilitada
grep "if False and self.user_query" app/agents/sql_tools.py

# Deve retornar uma linha com "if False"
```
