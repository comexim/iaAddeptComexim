"""
Modelos de usuário e permissões
"""
from pydantic import BaseModel, EmailStr
from typing import List, Literal


PermissionType = Literal[
    "Financeiro",
    "Estoque",
    "Vendas",
    "Compras",
    "Orçamento",
    "RH",
    "Fiscal",
    "Contábil"
]


class UserPermissions(BaseModel):
    """Modelo de permissões do usuário"""
    telefone: str
    nome: str
    email: EmailStr
    direitos: List[PermissionType]

    def has_permission(self, module: PermissionType) -> bool:
        """Verifica se usuário tem permissão para módulo"""
        return module in self.direitos

    def has_any_permission(self, modules: List[PermissionType]) -> bool:
        """Verifica se usuário tem pelo menos uma das permissões"""
        return any(module in self.direitos for module in modules)


class ProtheusAuthResponse(BaseModel):
    """Resposta da API Protheus de autenticação"""
    descrRet: str
    data: dict | None = None

    @property
    def is_authorized(self) -> bool:
        """Verifica se usuário está autorizado"""
        return self.descrRet != "Usuário não autorizado" and self.data is not None

    def to_user_permissions(self) -> UserPermissions | None:
        """Converte resposta para UserPermissions"""
        if not self.is_authorized or not self.data:
            return None

        return UserPermissions(
            telefone=self.data.get("telefone", ""),
            nome=self.data.get("nome", ""),
            email=self.data.get("mail", ""),
            direitos=self.data.get("direitos", [])
        )
