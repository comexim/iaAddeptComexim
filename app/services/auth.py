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

        # BYPASS: Marco - Cliente com acesso TOTAL
        if phone == "11915901500":
            logger.info(f"[BYPASS] Cliente Marco {phone} - ACESSO TOTAL")
            return UserPermissions(
                telefone="11915901500",
                nome="Marco",
                email="marco.souza@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Cliente teste com acesso TOTAL
        if phone == "54997076306":
            logger.info(f"[BYPASS] Cliente {phone} - ACESSO TOTAL")
            return UserPermissions(
                telefone="54997076306",
                nome="Cliente Teste",
                email="teste@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Renan Hazan - acesso TOTAL
        if phone == "13991386001":
            logger.info(f"[BYPASS] {phone} Renan Hazan - ACESSO TOTAL")
            return UserPermissions(
                telefone="13991386001",
                nome="Renan Hazan",
                email="renan.hazan@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Rodrigo Perez - acesso parcial
        if phone == "13991555279":
            logger.info(f"[BYPASS] {phone} Rodrigo Perez - ACESSO PARCIAL")
            return UserPermissions(
                telefone="13991555279",
                nome="Rodrigo Perez",
                email="rodrigo.perez@comexim.com.br",
                direitos=["Financeiro", "Vendas", "Compras", "Orçamento"]
            )

        # BYPASS: Bruno Hazan - acesso TOTAL
        if phone == "13988188810":
            logger.info(f"[BYPASS] {phone} Bruno Hazan - ACESSO TOTAL")
            return UserPermissions(
                telefone="13988188810",
                nome="Bruno Hazan",
                email="bruno@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Diego Salgado - sem RH
        if phone == "13997783898":
            logger.info(f"[BYPASS] {phone} Diego Salgado - ACESSO PARCIAL")
            return UserPermissions(
                telefone="13997783898",
                nome="Diego Salgado",
                email="diego.salgado@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "Fiscal", "Contábil"]
            )

        # BYPASS: Jonas Oshiro - sem RH
        if phone == "13988188962":
            logger.info(f"[BYPASS] {phone} Jonas Oshiro - ACESSO PARCIAL")
            return UserPermissions(
                telefone="13988188962",
                nome="Jonas Oshiro",
                email="jonas.oshiro@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "Fiscal", "Contábil"]
            )

        # BYPASS: Gilberto Silva - sem RH
        if phone == "13991758737":
            logger.info(f"[BYPASS] {phone} Gilberto Silva - ACESSO PARCIAL")
            return UserPermissions(
                telefone="13991758737",
                nome="Gilberto Silva",
                email="gilberto.silva@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "Fiscal", "Contábil"]
            )

        # BYPASS: Ricardo Cavalin - acesso TOTAL
        if phone == "13988190217":
            logger.info(f"[BYPASS] {phone} Ricardo Cavalin - ACESSO TOTAL")
            return UserPermissions(
                telefone="13988190217",
                nome="Ricardo Cavalin",
                email="ricardo.cavalin@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento", "RH", "Fiscal", "Contábil"]
            )

        # BYPASS: Mara Yadoya - sem RH, Fiscal, Contábil
        if phone == "13991758568":
            logger.info(f"[BYPASS] {phone} Mara Yadoya - ACESSO PARCIAL")
            return UserPermissions(
                telefone="13991758568",
                nome="Mara Yadoya",
                email="mara.yadoya@comexim.com.br",
                direitos=["Financeiro", "Estoque", "Vendas", "Compras", "Orçamento"]
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
