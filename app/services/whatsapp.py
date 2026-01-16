"""
Serviço de integração com Evolution API (WhatsApp)
"""
import httpx
import logging
from typing import List
from app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Serviço para enviar mensagens via Evolution API"""

    def __init__(self):
        self.base_url = settings.evolution_api_url
        self.token = settings.evolution_api_token

    async def send_text_message(self, phone: str, text: str) -> bool:
        """
        Envia mensagem de texto para WhatsApp

        Args:
            phone: Número de telefone (formato: 5511999999999@s.whatsapp.net)
            text: Texto da mensagem

        Returns:
            True se enviou com sucesso, False caso contrário
        """
        # Garante formato correto do telefone
        if not phone.endswith("@s.whatsapp.net"):
            phone = f"{phone}@s.whatsapp.net"

        # UAZAPI: /send/text
        url = f"{self.base_url}/send/text"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": self.token
        }
        payload = {
            "number": phone.replace("@s.whatsapp.net", ""),
            "text": text
        }

        logger.info(f"[WHATSAPP] Enviando mensagem para {phone}: {text[:100]}...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                logger.info(f"[WHATSAPP] Mensagem enviada com sucesso para {phone} - Status: {response.status_code}")
                logger.info(f"[WHATSAPP] Resposta da API: {response.text}")
                return True

        except httpx.HTTPError as e:
            logger.error(f"Erro ao enviar mensagem para {phone}: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar mensagem: {e}")
            return False

    async def send_multiple_messages(
        self,
        phone: str,
        messages: List[str],
        delay_seconds: int = 3
    ) -> int:
        """
        Envia múltiplas mensagens com delay entre elas

        Args:
            phone: Número de telefone
            messages: Lista de mensagens
            delay_seconds: Delay entre mensagens

        Returns:
            Número de mensagens enviadas com sucesso
        """
        import asyncio

        sent_count = 0
        for i, message in enumerate(messages):
            if message.strip():  # Ignora mensagens vazias
                success = await self.send_text_message(phone, message)
                if success:
                    sent_count += 1

                # Adiciona delay entre mensagens (exceto na última)
                if i < len(messages) - 1:
                    await asyncio.sleep(delay_seconds)

        logger.info(f"Enviadas {sent_count}/{len(messages)} mensagens para {phone}")
        return sent_count


# Instância global
whatsapp_service = WhatsAppService()
