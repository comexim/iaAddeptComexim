"""
Serviço de processamento de áudio (transcrição)
"""
import httpx
import logging
from openai import AsyncOpenAI
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class AudioService:
    """Serviço para processar áudio do WhatsApp"""

    def __init__(self):
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.evolution_base_url = settings.evolution_api_url
        self.evolution_token = settings.evolution_api_token

    async def download_audio(self, message_id: str) -> Optional[bytes]:
        """
        Baixa áudio do WhatsApp via Evolution API

        Args:
            message_id: ID da mensagem de áudio

        Returns:
            Bytes do arquivo de áudio ou None
        """
        url = f"{self.evolution_base_url}/message/download"
        headers = {"token": self.evolution_token}
        payload = {
            "id": message_id,
            "return_base64": False,
            "generate_mp3": True,
            "return_link": False,
            "transcribe": False
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Primeira request: obtém URL do arquivo
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                file_url = data.get("fileURL")
                if not file_url:
                    logger.error("fileURL não retornada pela API")
                    return None

                # Segunda request: baixa o arquivo
                logger.info(f"Baixando áudio de: {file_url}")
                file_response = await client.get(file_url, timeout=60.0)
                file_response.raise_for_status()

                logger.info(f"Áudio baixado com sucesso: {len(file_response.content)} bytes")
                return file_response.content

        except httpx.HTTPError as e:
            logger.error(f"Erro ao baixar áudio: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro inesperado ao baixar áudio: {e}")
            return None

    async def transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """
        Transcreve áudio usando OpenAI Whisper

        Args:
            audio_bytes: Bytes do arquivo de áudio

        Returns:
            Texto transcrito ou None
        """
        try:
            # Cria arquivo temporário em memória
            import io
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"

            logger.info("Iniciando transcrição com Whisper...")
            transcript = await self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="pt"
            )

            transcribed_text = transcript.text
            logger.info(f"Áudio transcrito: {transcribed_text[:100]}...")
            return transcribed_text

        except Exception as e:
            logger.error(f"Erro ao transcrever áudio: {e}")
            return None

    async def process_audio_message(self, message_id: str) -> Optional[str]:
        """
        Processo completo: download + transcrição

        Args:
            message_id: ID da mensagem de áudio

        Returns:
            Texto transcrito ou None
        """
        if not settings.enable_audio_transcription:
            logger.info("Transcrição de áudio desabilitada")
            return None

        audio_bytes = await self.download_audio(message_id)
        if not audio_bytes:
            return None

        transcribed_text = await self.transcribe_audio(audio_bytes)
        return transcribed_text


# Instância global
audio_service = AudioService()
