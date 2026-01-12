"""
Cliente Supabase para gerenciamento de preferências do usuário
"""
import logging
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from app.core.config import settings
from app.models.preferences import UserPreferences

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Cliente para operações no Supabase"""

    def __init__(self):
        self.url = settings.supabase_url
        self.key = settings.supabase_service_role_key
        self._client: Optional[Client] = None

    def get_client(self) -> Client:
        """Obtém cliente Supabase (singleton)"""
        if self._client is None:
            self._client = create_client(self.url, self.key)
            logger.info("Cliente Supabase inicializado")
        return self._client

    # ==========================================
    # User Preferences Operations
    # ==========================================

    async def get_user_preferences(self, telefone: str) -> Optional[UserPreferences]:
        """
        Busca preferências do usuário

        Args:
            telefone: Telefone do usuário

        Returns:
            UserPreferences ou None
        """
        try:
            client = self.get_client()
            response = client.table("user_preferences").select("*").eq("telefone", telefone).execute()

            if response.data and len(response.data) > 0:
                logger.info(f"Preferências encontradas para {telefone}")
                # Converte dict para UserPreferences
                data = response.data[0]
                return UserPreferences(**data)

            logger.info(f"Nenhuma preferência encontrada para {telefone}, usando padrão")
            return None

        except Exception as e:
            logger.error(f"Erro ao buscar preferências para {telefone}: {e}")
            return None

    async def create_user_preferences(
        self,
        telefone: str,
        nome: str = "",
        email: str = "",
        **kwargs
    ) -> Optional[UserPreferences]:
        """
        Cria preferências iniciais para usuário

        Args:
            telefone: Telefone do usuário
            nome: Nome do usuário
            email: Email do usuário
            **kwargs: Preferências adicionais

        Returns:
            UserPreferences criado
        """
        try:
            client = self.get_client()

            data = {
                "telefone": telefone,
                "nome": nome,
                "email": email,
                **kwargs
            }

            response = client.table("user_preferences").insert(data).execute()

            logger.info(f"Preferências criadas para {telefone}")
            if response.data:
                return UserPreferences(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"Erro ao criar preferências para {telefone}: {e}")
            return None

    async def update_user_preference(
        self,
        telefone: str,
        field: str,
        value: Any,
        learned_from: str = "user_feedback",
        confidence: float = 0.0
    ) -> bool:
        """
        Atualiza uma preferência específica

        Args:
            telefone: Telefone do usuário
            field: Campo a ser atualizado (ex: nivel_detalhe)
            value: Novo valor
            learned_from: Origem do aprendizado
            confidence: Nível de confiança (0-1)

        Returns:
            True se atualizado com sucesso
        """
        try:
            client = self.get_client()

            # Atualiza preferência
            update_data = {field: value}
            response = client.table("user_preferences").update(update_data).eq("telefone", telefone).execute()

            if response.data:
                logger.info(f"Preferência {field}={value} atualizada para {telefone} (confiança: {confidence})")
                return True

            logger.warning(f"Nenhuma linha atualizada para {telefone}")
            return False

        except Exception as e:
            logger.error(f"Erro ao atualizar preferência {field} para {telefone}: {e}")
            return False

    async def get_or_create_user_preferences(
        self,
        telefone: str,
        nome: str = "",
        email: str = ""
    ) -> UserPreferences:
        """
        Busca preferências ou cria se não existir

        Args:
            telefone: Telefone do usuário
            nome: Nome do usuário
            email: Email do usuário

        Returns:
            UserPreferences
        """
        prefs = await self.get_user_preferences(telefone)

        if prefs is None:
            logger.info(f"Criando preferências padrão para {telefone}")
            prefs = await self.create_user_preferences(telefone, nome, email)

        return prefs or self._get_default_preferences(telefone, nome, email)

    def _get_default_preferences(self, telefone: str, nome: str = "", email: str = "") -> UserPreferences:
        """Retorna preferências padrão"""
        return UserPreferences(
            telefone=telefone,
            nome=nome,
            email=email,
            nivel_detalhe="medio",
            tom_de_voz="profissional",
            formato_resposta="texto",
            formato_moeda="BRL",
            formato_data="DD/MM/YYYY",
            emojis_habilitados=True,
            areas_interesse=[],
            metricas_favoritas=[],
            learning_history=[],
            confidence_score=0.5,
            feedback_count=0
        )

    # ==========================================
    # Learning Log Operations
    # ==========================================

    async def log_feedback(
        self,
        telefone: str,
        feedback_type: str,
        detected_pattern: str,
        confidence_score: float,
        applied: bool,
        details: Dict[str, Any]
    ) -> bool:
        """
        Registra feedback do usuário no log

        Args:
            telefone: Telefone do usuário
            feedback_type: Tipo de feedback
            detected_pattern: Padrão detectado
            confidence_score: Score de confiança
            applied: Se foi aplicado
            details: Detalhes do feedback

        Returns:
            True se registrado com sucesso
        """
        try:
            client = self.get_client()

            data = {
                "telefone": telefone,
                "user_message": details.get("user_message", ""),
                "feedback_detected": details,
                "preference_updated": feedback_type,
                "old_value": str(details.get("old_value", "")),
                "new_value": str(details.get("valor", "")),
                "confidence": confidence_score,
                "applied": applied
            }

            client.table("preference_learning_log").insert(data).execute()

            logger.debug(f"Feedback registrado para {telefone}")
            return True

        except Exception as e:
            logger.error(f"Erro ao registrar feedback para {telefone}: {e}")
            return False

    async def get_learning_history(
        self,
        telefone: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Busca histórico de aprendizado

        Args:
            telefone: Telefone do usuário
            limit: Número de registros

        Returns:
            Lista de registros de aprendizado
        """
        try:
            client = self.get_client()

            response = (
                client.table("preference_learning_log")
                .select("*")
                .eq("telefone", telefone)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Erro ao buscar histórico para {telefone}: {e}")
            return []


# Instância global
supabase_client = SupabaseClient()
