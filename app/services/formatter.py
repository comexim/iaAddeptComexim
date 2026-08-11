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
from app.services.number_formatting import normalize_numbers_pt_br

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
        # Limpa links markdown/URLs antes de qualquer processamento
        text = self._limpar_markdown(text)

        # Respostas de falha da Z24 sao deterministicas. Nao as envie ao LLM
        # formatador, pois ele pode acrescentar uma oferta de Hedge que so e
        # permitida depois da confirmacao de sucesso da fixacao.
        if self._is_fixacao_error(text):
            text = self._remove_hedge_offer(text)
            logger.info("Preservando erro de fixacao sem formatacao por IA")
            return self._simple_split(text)

        # Este relatório contém uma lista completa calculada no backend.
        # Não passar por outro LLM, pois ele pode resumir ou omitir clientes.
        if (
            text.startswith("Resultados de contas a receber vencidas:")
            or text.startswith("Contas a receber vencidas do cliente ")
        ):
            logger.info("Formatando relatório vencido sem IA para preservar todos os clientes")
            return self._split_preservando_linhas(text)

        if not settings.enable_response_formatter:
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
            return self._simple_split(text)

    def _limpar_markdown(self, text: str) -> str:
        """Remove elementos markdown que não renderizam bem no WhatsApp."""
        import re
        text = text.replace("\\n\\n", "\n\n")
        # Remove confirmações internas de aprendizado/preferência que não
        # devem aparecer como mensagem normal no WhatsApp.
        text = re.sub(
            r'(?im)^\s*_?\[Prefer[êe]ncia\s+atualizada:[^\]]+\]_?\s*$',
            '',
            text,
        )
        # [texto](url) → texto
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # URLs soltas (http://... ou https://...) → remove
        text = re.sub(r'https?://\S+', '', text)
        return normalize_numbers_pt_br(text)

    def _simple_split(self, text: str) -> List[str]:
        """Split simples por parágrafos"""
        messages = [msg.strip() for msg in text.split("\n\n") if msg.strip()]
        return messages if messages else [text]

    def _is_fixacao_error(self, text: str) -> bool:
        """Reconhece a mensagem controlada de falha no cadastro da Z24."""
        import unicodedata
        normalized = unicodedata.normalize("NFKD", text)
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        return "nao foi possivel concluir o cadastro:" in normalized.lower()

    def _remove_hedge_offer(self, text: str) -> str:
        """Remove defensivamente convites de Hedge de uma resposta de erro."""
        import re
        return re.sub(
            r"(?is)(?:\s*\n+)?[^\n.!?]*\b(?:gostaria|quer|deseja)[^\n.!?]*\bhedge\b[^\n]*[?!.]?",
            "",
            text,
        ).strip()

    def _split_preservando_linhas(self, text: str, limite: int = 3500) -> List[str]:
        """Divide texto longo sem reescrever, resumir ou perder linhas."""
        partes: List[str] = []
        atual: List[str] = []
        tamanho = 0

        for linha in text.splitlines():
            acrescimo = len(linha) + (1 if atual else 0)
            if atual and tamanho + acrescimo > limite:
                partes.append("\n".join(atual).strip())
                atual = []
                tamanho = 0
            atual.append(linha)
            tamanho += len(linha) + (1 if len(atual) > 1 else 0)

        if atual:
            partes.append("\n".join(atual).strip())

        return [parte for parte in partes if parte]


# Instância global
response_formatter = ResponseFormatter()
