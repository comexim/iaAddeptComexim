# Debug do Erro em Produção - Saldo Bancário

## Situação Atual

**PROBLEMA**: O fix foi deployado com sucesso (verificado por grep), mas a IA ainda retorna erro ao consultar dados do Itaú Santos em produção.

**Verificações OK**:
- ✅ Commit cd1faf3 presente no servidor
- ✅ grep encontrou "FILTRADO AUTOMATICAMENTE" (1 ocorrência)
- ✅ grep encontrou "contratos_baixados_nov2025" (7 ocorrências)
- ✅ Serviço reiniciado com sucesso
- ✅ Todos os testes locais passaram (7/7 checks)

**Problema**:
- ❌ Produção retorna: "Desculpe, ocorreu um erro ao consultar os dados"
- ❌ Logs mostram: ToolMessage com erro genérico
- ❌ Exceção real está sendo capturada e não exibida

---

## O Que Foi Feito

### 1. Melhorias no Error Logging (app/agents/sql_tools.py)

Adicionei traceback completo em TODOS os handlers de erro:

```python
except Exception as e:
    import traceback
    logger.error(f"Erro ao executar IA_SaldoBancario: {e}")
    logger.error(f"Traceback completo: {traceback.format_exc()}")
    return f"Desculpe, ocorreu um erro ao consultar os dados. Por favor, tente novamente."
```

**Benefício**: Agora os logs mostrarão o traceback completo, facilitando debug futuro.

### 2. Script para Extrair Logs (check_prod_logs.sh)

Script para buscar o erro real nos logs existentes:

```bash
chmod +x check_prod_logs.sh
./check_prod_logs.sh
```

**O que faz**:
- Busca por "Erro ao executar IA_SaldoBancario" nos últimos 200 logs
- Busca por linhas de ERROR
- Busca por exceções Python (Traceback, Exception)
- Busca por logs relacionados a "saldo"

### 3. Script de Debug Direto (debug_prod_error.py)

Script para executar NO SERVIDOR e capturar a exceção exata:

```bash
cd /opt/agente-comexim-whatsapp
source venv/bin/activate
python3 debug_prod_error.py
```

**O que faz**:
- Simula exatamente a chamada que está falhando
- Captura e exibe o traceback completo
- Salva resultado em /tmp/debug_prod_result.txt
- Faz verificações automáticas

---

## Como Debugar - Passo a Passo

### Opção 1: Verificar Logs Existentes (RÁPIDO)

```bash
# No servidor
cd /opt/agente-comexim-whatsapp
./check_prod_logs.sh
```

Procure por:
- "Erro ao executar IA_SaldoBancario: [mensagem do erro]"
- "Traceback completo: [stack trace]"

### Opção 2: Executar Script de Debug (MAIS DETALHADO)

```bash
# No servidor
cd /opt/agente-comexim-whatsapp
source venv/bin/activate
python3 debug_prod_error.py
```

O script mostrará:
- Se imports funcionam
- Se UserPermissions é criado corretamente
- Se SQLTools é criado corretamente
- **O ERRO EXATO que está ocorrendo** com traceback completo

### Opção 3: Deploy da Melhoria de Logging (PARA O FUTURO)

```bash
# No seu PC
cd c:\Users\pedro\Desktop\agente-comexim
git add app/agents/sql_tools.py
git commit -m "Fix: adicionar traceback completo nos logs de erro para facilitar debug"
git push

# No servidor
cd /opt/agente-comexim-whatsapp
git pull
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
systemctl restart agente-comexim

# Testar novamente com a pergunta
# Depois ver os logs:
journalctl -u agente-comexim -n 100 --no-pager | grep -A 10 "Traceback completo"
```

---

## Possíveis Causas do Erro

### 1. Problema com Encoding
**Sintoma**: UnicodeDecodeError ou UnicodeEncodeError
**Causa**: Caracteres especiais (acentos, símbolos de moeda)
**Solução**: Verificar encoding='utf-8' em todas as operações de string

### 2. Problema com Banco de Dados
**Sintoma**: pyodbc.Error ou SQL Server error
**Causa**: Conexão, timeout, ou erro na query SQL
**Solução**: Verificar conexão, credentials, e query gerada

### 3. Problema com JSON
**Sintoma**: json.JSONDecodeError
**Causa**: Formato inválido ao tentar parsear resultado
**Solução**: Verificar formato dos dados retornados do banco

### 4. Problema com Regex
**Sintoma**: re.error ou AttributeError
**Causa**: Padrão regex inválido ou string None
**Solução**: Validar self.user_query antes de usar regex

### 5. Problema com Importação
**Sintoma**: ImportError ou ModuleNotFoundError
**Causa**: Módulo não instalado ou path incorreto
**Solução**: Verificar venv e requirements.txt

---

## Checklist de Verificação

Após executar debug_prod_error.py, verifique:

- [ ] Imports funcionaram? (se não, problema de dependências)
- [ ] UserPermissions criado? (se não, problema de validação)
- [ ] SQLTools criado? (se não, problema de inicialização)
- [ ] Query executada? (se não, veja o traceback para causa exata)
- [ ] Resultado contém erro? (se sim, erro vem do próprio código SQL ou formatação)
- [ ] Filtro automático aplicado? (se não, regex não está detectando bancos)
- [ ] BB e ITAU presentes? (se não, filtro não está funcionando)

---

## Arquivos Criados

1. **debug_prod_error.py** - Script Python para debug direto no servidor
2. **check_prod_logs.sh** - Script Bash para extrair erros dos logs
3. **DEBUG_PRODUCAO.md** - Este arquivo de documentação
4. **app/agents/sql_tools.py** - Melhorado com traceback completo em logs

---

## Próximos Passos

1. Execute `debug_prod_error.py` no servidor para ver o erro exato
2. Com base no erro, aplique a correção apropriada
3. Teste novamente em produção
4. Se o problema persistir, compartilhe o output completo do debug_prod_error.py
