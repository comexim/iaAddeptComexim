"""Models"""
from app.models.user import UserPermissions, ProtheusAuthResponse, PermissionType
from app.models.message import WhatsAppMessage, EvolutionWebhookPayload

__all__ = [
    "UserPermissions",
    "ProtheusAuthResponse",
    "PermissionType",
    "WhatsAppMessage",
    "EvolutionWebhookPayload",
]
