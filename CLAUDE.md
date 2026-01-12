# CLAUDE.md - Configurações e Instruções do Claude Code

## 1. Agentes Disponíveis

### 1.1 Agentes de Processamento de Prompts
Todos os agentes listados abaixo **devem obrigatoriamente** utilizar o sequential-thinking para processamento estruturado.

#### validador_estrutura_prompts
- **Função**: Valida prompts contra padrões estruturais estabelecidos
- **Quando usar**: Verificar conformidade com padrões de qualidade antes da implementação
- **Exemplo**: "Valide se meu prompt está seguindo os padrões corretos"

#### revisor_de_estrutura_de_prompts
- **Função**: Revisa a qualidade estrutural dos prompts
- **Quando usar**: Analisar estrutura, formatação e aderência às melhores práticas
- **Exemplo**: "Revise a estrutura deste prompt quanto à qualidade"

#### migrador_estrutura_prompts
- **Função**: Migra prompts existentes para novos padrões estruturais
- **Quando usar**: Converter prompts legados ou não estruturados para formato padronizado
- **Exemplo**: "Migre este prompt antigo para o novo padrão"

#### gerador_estrutura_prompts
- **Função**: Gera estrutura base para novos prompts
- **Quando usar**: Criar novos prompts de assistente com seções apropriadas
- **Exemplo**: "Crie a estrutura base para um novo assistente"

#### otimizador_de_prompt
- **Função**: Otimiza prompts com base em feedback
- **Quando usar**: Melhorar prompts existentes incorporando feedback do usuário
- **Exemplo**: "Otimize meu prompt com base no feedback recebido"

### 1.2 Agente de Propósito Geral

#### general-purpose
- **Função**: Pesquisa complexa e execução de tarefas multi-etapas
- **Quando usar**: Pesquisar arquivos, entender estrutura de código, tarefas complexas
- **Requisito**: Uso obrigatório de sequential-thinking

## 2. Configuração MCP (Model Context Protocol)

### 2.1 Servidores MCP Disponíveis

#### 1. Exa AI Search (`mcp__exa`)
**Capacidades de pesquisa avançada com IA:**
- `web_search_exa`: Pesquisas web em tempo real
- `company_research_exa`: Pesquisa detalhada de empresas
- `crawling_exa`: Extração de conteúdo de URLs
- `linkedin_search_exa`: Pesquisa no LinkedIn
- `deep_researcher_start`: Iniciar pesquisa profunda com IA
- `deep_researcher_check`: Verificar status de pesquisa

#### 2. Supabase Community (`mcp__supabase-community-supabase-mcp`)
**Gerenciamento completo de banco de dados:**
- Gerenciamento de branches de desenvolvimento
- Operações de banco de dados (tabelas, extensões, migrações)
- Documentação via GraphQL
- Edge Functions
- Ferramentas de projeto (logs, advisors, keys)

#### 3. Browserbase (`mcp__mcp-browserbase`)
**Automação de navegador com Stagehand:**
- **Sessão única**: `browserbase_session_create`, `browserbase_session_close`
- **Multi-sessão**: `multi_browserbase_stagehand_session_create`, `multi_browserbase_stagehand_session_list`, `multi_browserbase_stagehand_session_close`
- **Navegação**: `browserbase_stagehand_navigate`, `multi_browserbase_stagehand_navigate_session`
- **Interação**: `browserbase_stagehand_act`, `multi_browserbase_stagehand_act_session`
- **Extração**: `browserbase_stagehand_extract`, `multi_browserbase_stagehand_extract_session`
- **Observação**: `browserbase_stagehand_observe`, `multi_browserbase_stagehand_observe_session`
- **Screenshots**: `browserbase_screenshot`
- Recursos salvos: Screenshots de sessões anteriores

#### 4. Sequential Thinking (`mcp__server-sequential-thinking`)
**Processamento cognitivo estruturado:**
- `sequentialthinking`: Análise passo a passo com revisão dinâmica
- Geração e verificação de hipóteses
- Revisão dinâmica de pensamento
- Resolução iterativa de problemas

#### 5. Redis MCP (`mcp__mcp-redis`)
**Gerenciamento completo de Redis:**
- **Operações gerais**: `dbsize`, `info`, `client_list`, `delete`, `type`, `expire`, `rename`
- **Busca de chaves**: `scan_keys`, `scan_all_keys`
- **Índices vetoriais**: `get_indexes`, `get_index_info`, `get_indexed_keys_number`, `create_vector_index_hash`, `vector_search_hash`
- **Hashes**: `hset`, `hget`, `hdel`, `hgetall`, `hexists`, `set_vector_in_hash`, `get_vector_from_hash`
- **Listas**: `lpush`, `rpush`, `lpop`, `rpop`, `lrange`, `llen`
- **Strings**: `set`, `get`
- **JSON**: `json_set`, `json_get`, `json_del`
- **Sorted Sets**: `zadd`, `zrange`, `zrem`
- **Sets**: `sadd`, `srem`, `smembers`
- **Streams**: `xadd`, `xrange`, `xdel`
- **Pub/Sub**: `publish`, `subscribe`, `unsubscribe`

#### 6. Context7 Documentation (`mcp__context7-mcp`)
**Documentação de bibliotecas:**
- `resolve-library-id`: Resolução de IDs de pacotes
- `get-library-docs`: Recuperação de documentação atualizada

#### 7. VS Code Integration (`mcp__ide`)
**Integração com IDE:**
- `getDiagnostics`: Diagnósticos de linguagem
- `executeCode`: Execução de código Python/Jupyter

### 2.2 Adicionando Novos Servidores

```bash
claude mcp add <nome-do-servidor>
```

## 3. Regras de Uso do Sequential-Thinking

### 3.1 Aplicação Obrigatória

O sequential-thinking (`mcp__server-sequential-thinking__sequentialthinking`) é **mandatório** para todas as operações que envolvam:

- Análise e validação de código ou texto
- Tomada de decisões complexas
- Planejamento e execução de tarefas
- Resolução de problemas multi-etapas
- Processamento estruturado de informações
- Geração e verificação de conteúdo

### 3.2 Metodologia de Implementação

1. Iniciar sempre com sequential-thinking antes de qualquer ação
2. Estruturar o pensamento em etapas claras
3. Permitir revisões e ajustes durante o processo
4. Gerar e verificar hipóteses
5. Iterar até alcançar solução satisfatória

### 3.3 Casos de Uso Críticos

- Decomposição de problemas complexos
- Planejamento com espaço para revisão
- Análises que requerem correção de curso
- Problemas com escopo inicialmente indefinido
- Manutenção de contexto em tarefas longas
- Filtragem de informações irrelevantes

## 4. Instruções Essenciais de Operação

### 4.1 Princípios Fundamentais

- **Fazer exatamente o que foi solicitado**: nem mais, nem menos
- **Documentação apenas sob demanda**: nunca criar arquivos .md ou README proativamente

### 4.2 Gerenciamento de Arquivos

- Criar ou editar arquivos conforme necessário para o objetivo
- Documentação (*.md, README) apenas mediante solicitação explícita

### 4.3 Configurações Adicionais

- **Task Manager**: Sempre usar para necessidades do usuário
- **Visualização**: Exibir lista de tarefas em formato tabular
- **Feedback**: Considerar hooks e feedback como vindos diretamente do usuário

## 5. Observações Importantes

**Nota sobre falhas**: A não utilização do sequential-thinking quando requerido é considerada uma falha crítica do sistema.

**Contexto**: Este arquivo pode conter múltiplas versões ou duplicações. Sempre considerar a versão mais recente e completa.