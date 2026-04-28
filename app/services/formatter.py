"""
Serviço de formatação de respostas para WhatsApp
"""
import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.prompts.system_prompt import FORMATTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formata respostas longas em mensagens curtas para WhatsApp"""

    def __init__(self):
        # Usa modelo menor e mais barato para formatação
        if settings.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=settings.formatter_model,
                temperature=settings.formatter_temperature,
                api_key=settings.openai_api_key
            )
        else:
            self.llm = ChatAnthropic(
                model=settings.formatter_model,
                temperature=settings.formatter_temperature,
                api_key=settings.anthropic_api_key
            )

    async def format_response(self, text: str) -> List[str]:
        """
        Formata resposta longa em múltiplas mensagens curtas

        Args:
            text: Texto original da resposta

        Returns:
            Lista de mensagens formatadas
        """
        if not settings.enable_response_formatter:
            # Se formatador está desabilitado, apenas quebra por \n\n
            return self._simple_split(text)

        try:
            logger.info("Formatando resposta com AI...")

            messages = [
                SystemMessage(content=FORMATTER_SYSTEM_PROMPT),
                HumanMessage(content=f"Mensagem original para formatação: {text}")
            ]

            response = await self.llm.ainvoke(messages)
            formatted_text = self._limpar_markdown(response.content)

            # Split por \n\n
            messages_list = [
                msg.strip()
                for msg in formatted_text.split("\n\n")
                if msg.strip()
            ]

            logger.info(f"Resposta formatada em {len(messages_list)} mensagens")
            return messages_list

        except Exception as e:
            logger.error(f"Erro ao formatar resposta: {e}")
            # Fallback: split simples
            return self._simple_split(text)

    def _limpar_markdown(self, text: str) -> str:
        """Remove elementos markdown que não renderizam bem no WhatsApp."""
        import re
        # [texto](url) → texto
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # URLs soltas (http://... ou https://...) → remove
        text = re.sub(r'https?://\S+', '', text)
        return text

    def _simple_split(self, text: str) -> List[str]:
        """Split simples por parágrafos"""
        messages = [msg.strip() for msg in text.split("\n\n") if msg.strip()]
        return messages if messages else [text]


# Instância global
response_formatter = ResponseFormatter()
