# Tabela de Usuários e Permissões

## Estrutura de Dados

Cada usuário possui um telefone (identificador único) e permissões específicas para acessar diferentes módulos do sistema.

## Campos de Permissões (Direitos)

- **Financeiro**: Acesso a dados financeiros gerais
- **Estoque**: Acesso a informações de estoque
- **Vendas**: Acesso a dados de vendas
- **Compras**: Acesso a informações de compras
- **Orçamento**: Acesso a orçamentos
- **RH**: Acesso a dados de recursos humanos
- **Fiscal**: Acesso a informações fiscais
- **Contábil**: Acesso a dados contábeis

**Legenda**: `S` = Sim (tem permissão), `N` = Não (sem permissão)

## Usuários Cadastrados

| Telefone | Nome | Email | Financeiro | Estoque | Vendas | Compras | Orçamento | RH | Fiscal | Contábil |
|----------|------|-------|------------|---------|--------|---------|-----------|----|---------|---------|
| 11915901500 | Marco Aurélio | marco.souza@comexim.com.br | S | S | S | S | S | S | S | S |
| 13991386001 | Renan Hazan | renan.hazan@comexim.com.br | S | S | S | S | S | S | S | S |
| 35920000589 | Lucas Oliveira | lucas.oliveira@comexim.com.br | S | S | S | S | S | S | S | S |
| 13991555279 | Rodrigo Perez | rodrigo.perez@comexim.com.br | S | N | S | S | S | N | N | N |
| 13988188810 | Bruno Hazan | bruno@comexim.com.br | S | S | S | S | S | S | S | S |

## Observações

1. **Autenticação**: Sistema valida usuário pelo número de telefone via API Protheus (`/iaProtheus/getToken`)
2. **Formato telefone**: No N8N, telefone vem com prefixo (+55). Sistema remove automaticamente.
3. **Permissões granulares**: Cada módulo pode ser habilitado/desabilitado individualmente.

## Casos de Uso

### Exemplo 1: Marco Aurélio (Acesso Total)
- Pode consultar qualquer função SQL
- Pode solicitar relatórios de qualquer categoria
- Acesso completo a todos os módulos

### Exemplo 2: Rodrigo Perez (Acesso Parcial)
- ✅ Pode consultar: Vendas, Compras, Orçamento, Financeiro
- ❌ Bloqueado: Estoque, RH, Fiscal, Contábil
- Se tentar acessar módulo bloqueado, sistema deve negar

## Integração com Banco de Dados

### Estrutura Sugerida (Python)

```python
# models/user.py
from pydantic import BaseModel
from typing import List

class UserPermissions(BaseModel):
    telefone: str
    nome: str
    email: str
    direitos: List[str]  # ["Financeiro", "Vendas", ...]

    def has_permission(self, module: str) -> bool:
        """Verifica se usuário tem permissão para módulo"""
        return module in self.direitos

# Mapeamento SQL Functions → Permissões
FUNCTION_PERMISSIONS = {
    "IA_Vendas": "Vendas",
    "IA_Compras": "Compras",
    "IA_ContasPagas": "Financeiro",
    "IA_ContasAPagar": "Financeiro",
    "IA_SaldoBancario": "Financeiro",
    "IA_Estoque": "Estoque",
    "IA_Orcamento": "Orçamento"
}
```

### Validação de Acesso

```python
def validate_access(user: UserPermissions, function_name: str) -> bool:
    """Valida se usuário pode executar função SQL"""
    required_permission = FUNCTION_PERMISSIONS.get(function_name)

    if not required_permission:
        return False

    return user.has_permission(required_permission)
```

## API Protheus Response (Esperado)

```json
{
  "descrRet": "Usuário autorizado",
  "data": {
    "nome": "Marco Aurélio",
    "mail": "marco.souza@comexim.com.br",
    "direitos": ["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
  }
}
```

ou

```json
{
  "descrRet": "Usuário não autorizado"
}
```
