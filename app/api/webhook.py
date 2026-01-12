"""
Webhook handler para Evolution API
"""
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.models.message import EvolutionWebhookPayload, WhatsAppMessage
from app.services.auth import auth_service
from app.services.whatsapp import whatsapp_service
from app.services.audio import audio_service
from app.services.formatter import response_formatter
from app.core.redis_client import redis_client
from app.agents.orchestrator import AgentOrchestrator
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class WebhookRequest(BaseModel):
    """Modelo de request do webhook"""
    body: dict  # Payload genérico do Evolution


async def process_message_flow(phone: str, message_text: str, session_id: str):
    """
    Fluxo completo de processamento de mensagem

    Args:
        phone: Telefone do usuário
        message_text: Texto da mensagem
        session_id: ID da sessão (chatid completo)
    """
    try:
        # 1. Autenticação
        logger.info(f"Iniciando processamento para {phone}")
        user = await auth_service.authenticate_user(phone)

        if not user:
            logger.warning(f"Usuário {phone} não autorizado")
            await whatsapp_service.send_text_message(
                session_id,
                "Acesso não autorizado."
            )
            return

        # 2. Sistema Anti-Flood: Adiciona mensagem ao buffer
        await redis_client.push_message(session_id, message_text)
        logger.info(f"Mensagem adicionada ao buffer de {phone}")

        # 3. Aguarda período anti-flood
        await asyncio.sleep(settings.anti_flood_wait_seconds)

        # 4. Recupera todas as mensagens do buffer
        buffered_messages = await redis_client.get_buffered_messages(session_id)

        # 5. Verifica se ainda tem mensagens (usuário parou de enviar)
        if not buffered_messages or buffered_messages[-1] != message_text:
            logger.info(f"Usuário {phone} ainda está enviando mensagens. Aguardando...")
            return

        # 6. Limpa buffer
        await redis_client.clear_buffer(session_id)

        # 7. Junta todas as mensagens
        full_message = ", ".join(buffered_messages)
        logger.info(f"Processando mensagem completa: {full_message[:100]}...")

        # 8. Cria orquestrador e processa
        orchestrator = AgentOrchestrator(user=user, session_id=phone)
        response = await orchestrator.process_message(full_message)

        # 9. Formata resposta
        formatted_messages = await response_formatter.format_response(response)

        # 10. Envia mensagens
        await whatsapp_service.send_multiple_messages(
            session_id,
            formatted_messages,
            delay_seconds=settings.message_delay_seconds
        )

        logger.info(f"Processamento concluído para {phone}")

    except Exception as e:
        logger.error(f"Erro no processamento da mensagem: {e}", exc_info=True)
        try:
            await whatsapp_service.send_text_message(
                session_id,
                "Desculpe, ocorreu um erro ao processar sua mensagem."
            )
        except:
            pass


@router.post("/webhook/evolution")
async def evolution_webhook(request: dict, background_tasks: BackgroundTasks):
    """
    Endpoint webhook para Evolution API

    Args:
        request: Payload do webhook
        background_tasks: FastAPI background tasks

    Returns:
        Status da operação
    """
    try:
        # DEBUG: Log completo do payload recebido
        logger.info(f"[WEBHOOK] Payload recebido: {request}")

        # Valida se é mensagem
        event_type = request.get("EventType") or request.get("event")
        logger.info(f"[WEBHOOK] EventType detectado: {event_type}")

        if event_type != "messages" and event_type != "messages.upsert":
            logger.info(f"[WEBHOOK] Evento ignorado: {event_type}")
            return {"status": "ignored", "reason": "not_a_message_event"}

        # Parse payload
        logger.info(f"[WEBHOOK] Tentando parsear payload...")
        payload = EvolutionWebhookPayload(**request)
        message = payload.to_whatsapp_message()
        logger.info(f"[WEBHOOK] Mensagem parseada: phone={message.phone_number}, text={message.text[:50] if message.text else 'None'}")

        # Filtros
        if message.from_me:
            logger.info(f"[WEBHOOK] Mensagem enviada pelo bot, ignorando")
            return {"status": "ignored", "reason": "from_me"}

        # Processa apenas texto e áudio
        if not (message.is_text or message.is_audio):
            logger.info(f"[WEBHOOK] Tipo de mensagem não suportado: {message.message_type}")
            return {"status": "ignored", "reason": "unsupported_message_type"}

        # Extrai texto
        text = message.text

        # Se for áudio, transcreve
        if message.is_audio:
            logger.info(f"Processando áudio de {message.phone_number}")
            transcribed = await audio_service.process_audio_message(message.message_id)
            if transcribed:
                text = f"Áudio: {transcribed}"
            else:
                await whatsapp_service.send_text_message(
                    message.chatid,
                    "Desculpe, não consegui processar o áudio. Tente enviar uma mensagem de texto."
                )
                return {"status": "error", "reason": "audio_transcription_failed"}

        # Valida texto
        if not text or not text.strip():
            logger.warning(f"[WEBHOOK] Mensagem vazia recebida")
            return {"status": "ignored", "reason": "empty_message"}

        logger.info(f"[WEBHOOK] Agendando processamento em background para {message.phone_number}")

        # Processa em background
        background_tasks.add_task(
            process_message_flow,
            message.phone_number,
            text.strip(),
            message.chatid
        )

        logger.info(f"[WEBHOOK] Processamento agendado com sucesso")
        return {"status": "processing"}

    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "agente-comexim",
        "version": "1.0.0"
    }
