"""
Orquestrador principal do agente usando LangGraph
"""
import logging
from typing import Optional, Sequence
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.supabase_client import supabase_client
from app.models.user import UserPermissions
from app.agents.sql_tools import SQLTools
from app.prompts.system_prompt import get_system_prompt, get_current_date_info
from app.services.preference_learning import preference_learning

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orquestrador principal do agente de IA"""

    def __init__(self, user: UserPermissions, session_id: str):
        """
        Inicializa orquestrador para usuário específico

        Args:
            user: Dados e permissões do usuário
            session_id: ID da sessão (telefone)
        """
        self.user = user
        self.session_id = session_id
        self.user_preferences = None  # Carregado sob demanda
        self.system_prompt = ""  # Carregado quando agente é criado

        # Inicializa LLM
        if settings.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=settings.ai_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                api_key=settings.openai_api_key
            )
        else:
            self.llm = ChatAnthropic(
                model=settings.ai_model,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens,
                api_key=settings.anthropic_api_key
            )

        # Cria tools SQL específicas para este usuário
        sql_tools = SQLTools(user)
        self.tools = sql_tools.get_all_tools()

        # Configura memória com Redis
        self.message_history = self._setup_memory()

        # Cria agente (será recriado quando preferências mudarem)
        self.agent = None

        logger.info(f"Orquestrador inicializado para usuário {user.nome} (sessão: {session_id})")

    def _setup_memory(self) -> RedisChatMessageHistory:
        """Configura memória de conversação com Redis"""
        message_history = RedisChatMessageHistory(
            session_id=f"{self.session_id}_memory_comexim",
            url=settings.redis_url,
            ttl=settings.redis_memory_ttl
        )
        return message_history

    async def _load_user_preferences(self):
        """Carrega preferências do usuário do Supabase"""
        if not settings.enable_preference_learning:
            return

        try:
            self.user_preferences = await supabase_client.get_or_create_user_preferences(
                telefone=self.session_id,
                nome=self.user.nome,
                email=self.user.email
            )
            logger.info(f"Preferências carregadas: {self.user_preferences.get_summary()}")
        except Exception as e:
            logger.error(f"Erro ao carregar preferências: {e}")
            self.user_preferences = None

    async def _create_agent(self):
        """Cria agente LangGraph com tools e memória"""
        # Carrega preferências do usuário
        await self._load_user_preferences()

        # System prompt base
        current_date = get_current_date_info()
        base_prompt = get_system_prompt(
            user_name=self.user.nome,
            user_email=self.user.email,
            current_date=current_date
        )

        # Injeta instruções personalizadas de preferências
        if self.user_preferences:
            custom_instructions = self.user_preferences.get_custom_instructions()
            system_prompt = f"""{base_prompt}

# INSTRUÇÕES PERSONALIZADAS DO USUÁRIO

{custom_instructions}

IMPORTANTE: Siga RIGOROSAMENTE as instruções personalizadas acima ao formatar suas respostas."""
        else:
            system_prompt = base_prompt

        # Cria agente LangGraph com ReAct pattern
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools
        )

        # Salva system prompt para usar nas mensagens
        self.system_prompt = system_prompt

        return self.agent

    async def process_message(self, message: str) -> str:
        """
        Processa mensagem do usuário

        Args:
            message: Mensagem do usuário

        Returns:
            Resposta do agente
        """
        try:
            # Armazena mensagem do usuário nas tools SQL para extração de cliente
            sql_tools = SQLTools(self.user)

            # CONTEXTO INTELIGENTE: Se mensagem curta, concatena com última pergunta do usuário
            contextualized_query = message
            logger.info(f"[CONTEXTO] Tamanho da mensagem: {len(message)} chars: '{message}'")

            if len(message) < 40:  # Aumentado para 40 para pegar respostas curtas
                # Recupera histórico
                history_messages = self.message_history.messages
                # Procura última pergunta do usuário (HumanMessage) que não seja essa
                for msg in reversed(history_messages):
                    if isinstance(msg, HumanMessage) and len(msg.content) > 40:
                        # Encontrou pergunta anterior completa
                        contextualized_query = f"{msg.content} {message}"
                        logger.info(f"[CONTEXTO] Mensagem curta detectada! Contextualizando com pergunta anterior...")
                        logger.info(f"[CONTEXTO] Resultado: '{contextualized_query[:200]}'")
                        break

            sql_tools.user_query = contextualized_query
            sql_tools.user_query_original = message  # Query SEM contexto para filtros
            self.tools = sql_tools.get_all_tools()

            logger.info(f"Processando mensagem do usuário {self.user.nome}: {message[:100]}...")

            # 1. Detecta e aplica feedback sobre preferências
            feedbacks_detected = []
            preferences_changed = False

            if settings.enable_preference_learning:
                feedbacks_detected, preferences_changed = await preference_learning.process_user_message(
                    user_message=message,
                    telefone=self.session_id
                )

                # Se preferências mudaram, recria agente com novo prompt
                if preferences_changed:
                    logger.info(f"Preferências atualizadas, recriando agente...")
                    self.agent = await self._create_agent()

            # 2. Cria agente se ainda não existe (primeira mensagem)
            if self.agent is None:
                self.agent = await self._create_agent()

            # 3. Recupera histórico de mensagens do Redis
            history_messages = self.message_history.messages

            # Limita histórico para últimos N mensagens (janela deslizante)
            max_history = settings.redis_memory_window * 2  # user + assistant = 2 messages
            if len(history_messages) > max_history:
                history_messages = history_messages[-max_history:]

            # 4. Prepara mensagens para o agente
            messages = []
            # Adiciona system prompt como primeira mensagem
            messages.append(SystemMessage(content=self.system_prompt))
            for msg in history_messages:
                messages.append(msg)
            messages.append(HumanMessage(content=message))

            # 5. Invoca agente
            config = {"configurable": {"thread_id": self.session_id}}
            response = await self.agent.ainvoke(
                {"messages": messages},
                config=config
            )

            # 6. Extrai resposta
            output_messages = response.get("messages", [])
            logger.info(f"[DEBUG] Total de mensagens retornadas: {len(output_messages)}")

            for idx, msg in enumerate(output_messages):
                msg_type = type(msg).__name__
                content_preview = str(msg.content)[:200] if hasattr(msg, 'content') else str(msg)[:200]
                logger.info(f"[DEBUG] Mensagem {idx}: Tipo={msg_type}, Content={content_preview}")

            if output_messages:
                last_message = output_messages[-1]
                if isinstance(last_message, AIMessage):
                    output = last_message.content
                else:
                    output = last_message.content
            else:
                output = "Desculpe, não consegui gerar uma resposta."

            # Garante que output é sempre string
            if isinstance(output, list):
                # Se for lista, pega apenas content type "text"
                text_parts = []
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                    else:
                        text_parts.append(str(item))
                output = "\n\n".join(p for p in text_parts if p)
                if not output:
                    output = "Desculpe, não consegui gerar uma resposta."
            elif not isinstance(output, str):
                # Converte qualquer outro tipo para string
                output = str(output) if output else "Desculpe, não consegui gerar uma resposta."

            # 7. Salva mensagens no histórico do Redis
            self.message_history.add_user_message(message)
            self.message_history.add_ai_message(output)

            # Remove prefixos de erro amigável
            if output.startswith("PRECISA_PERGUNTAR:"):
                output = output.replace("PRECISA_PERGUNTAR:", "").strip()

            # 8. Se detectou feedback de alta confiança, confirma aprendizado
            if feedbacks_detected and any(f.deve_aplicar for f in feedbacks_detected):
                confirmations = []
                for fb in feedbacks_detected:
                    if fb.deve_aplicar:
                        confirmations.append(f"{fb.tipo} → {fb.valor}")

                if confirmations:
                    output += f"\n\n_[Preferência atualizada: {', '.join(confirmations)}]_"

            logger.info(f"Resposta gerada: {output[:100]}...")
            logger.info(f"[DEBUG] Retornando output com {len(output)} caracteres")
            return output

        except Exception as e:
            logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
            logger.error(f"[DEBUG] Exception type: {type(e).__name__}")
            logger.error(f"[DEBUG] Exception args: {e.args}")
            return "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente."

    async def clear_memory(self):
        """Limpa memória da conversação"""
        self.message_history.clear()
        logger.info(f"Memória limpa para sessão {self.session_id}")
