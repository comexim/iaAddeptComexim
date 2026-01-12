"""
Serviço de autenticação via API Protheus
"""
import httpx
import logging
from typing import Optional
from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.user import UserPermissions, ProtheusAuthResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Serviço de autenticação de usuários"""

    def __init__(self):
        self.protheus_url = settings.protheus_token_url
        self.cache_ttl = 3600  # 1 hora

    async def authenticate_user(self, phone: str) -> Optional[UserPermissions]:
        """
        Autentica usuário via API Protheus

        Args:
            phone: Número de telefone (sem prefixos)

        Returns:
            UserPermissions se autorizado, None caso contrário
        """
        # BYPASS: Usuário de teste com acesso TOTAL
        # Telefone já vem sem o prefixo 55 (normalizado em message.py)
        if phone == "6182563956":
            logger.info(f"[BYPASS] Usuário teste {phone} - ACESSO TOTAL")
            return UserPermissions(
                telefone="6182563956",
                nome="Pedro Teste",
                email="pedro.teste@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Cliente com acesso TOTAL
        if phone == "35920000589":
            logger.info(f"[BYPASS] Cliente {phone} - ACESSO TOTAL")
            return UserPermissions(
                telefone="35920000589",
                nome="Cliente Comexim",
                email="cliente@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # Verifica cache primeiro
        cached = await redis_client.get_cached_user(phone)
        if cached:
            logger.info(f"Usuário {phone} encontrado no cache")
            return UserPermissions(**cached)

        # Se não está no cache, consulta API Protheus
        logger.info(f"Autenticando usuário {phone} via API Protheus...")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.protheus_url,
                    json={"telefone": phone}
                )
                response.raise_for_status()

                auth_response = ProtheusAuthResponse(**response.json())

                if not auth_response.is_authorized:
                    logger.warning(f"Usuário {phone} não autorizado: {auth_response.descrRet}")
                    return None

                user_permissions = auth_response.to_user_permissions()

                if user_permissions:
                    # Adiciona telefone ao model se não veio da API
                    if not user_permissions.telefone:
                        user_permissions.telefone = phone

                    # Cacheia usuário
                    await redis_client.cache_user(
                        phone,
                        user_permissions.model_dump(),
                        ttl=self.cache_ttl
                    )

                    logger.info(f"Usuário {phone} autenticado com sucesso: {user_permissions.nome}")
                    return user_permissions

                logger.error(f"Erro ao converter resposta para UserPermissions")
                return None

        except httpx.HTTPError as e:
            logger.error(f"Erro HTTP ao autenticar usuário {phone}: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao autenticar usuário {phone}: {e}")
            return None

    async def validate_access(
        self,
        user: UserPermissions,
        required_permission: str
    ) -> bool:
        """
        Valida se usuário tem permissão necessária

        Args:
            user: Usuário autenticado
            required_permission: Permissão necessária

        Returns:
            True se tem permissão, False caso contrário
        """
        has_permission = user.has_permission(required_permission)

        if not has_permission:
            logger.warning(
                f"Usuário {user.nome} ({user.telefone}) não tem permissão: {required_permission}"
            )

        return has_permission


# Instância global
auth_service = AuthService()
