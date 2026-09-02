"""Bloqueios antecipados para intenções de módulo identificáveis sem IA."""

import re
import unicodedata
from typing import Optional, Protocol


class PermissionUser(Protocol):
    def has_permission(self, module: str) -> bool: ...


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).lower()


def get_early_permission_denial(
    user: PermissionUser,
    message: str,
) -> Optional[str]:
    """Nega módulos explícitos antes de criar agente ou chamar qualquer LLM."""
    text = _normalize(message)
    purchase_intent = bool(
        re.search(
            r"\b(?:compra|compras|comprado|comprados|comprada|compradas|comprar|comprou|"
            r"aquisicao|aquisicoes)\b",
            text,
        )
    )

    if purchase_intent and not user.has_permission("Compras"):
        return "Você não tem permissão para acessar informações de Compras."

    return None
