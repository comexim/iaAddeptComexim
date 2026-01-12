"""
Modelos de mensagens WhatsApp
"""
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime


class WhatsAppMessage(BaseModel):
    """Mensagem recebida do WhatsApp"""
    chatid: str  # Telefone com @s.whatsapp.net
    sender: str
    sender_name: str
    text: str
    message_type: Literal["Conversation", "AudioMessage", "ImageMessage", "ExtendedTextMessage"]
    message_id: str
    timestamp: int
    from_me: bool = False

    @property
    def phone_number(self) -> str:
        """Extrai número de telefone limpo"""
        # Remove @s.whatsapp.net, @lid e prefixos
        phone = self.chatid.replace("@s.whatsapp.net", "").replace("@lid", "")
        if phone.startswith("+55"):
            phone = phone[3:]
        elif phone.startswith("55"):
            phone = phone[2:]
        return phone

    @property
    def is_audio(self) -> bool:
        return self.message_type == "AudioMessage"

    @property
    def is_text(self) -> bool:
        return self.message_type in ["Conversation", "ExtendedTextMessage"]


class EvolutionWebhookPayload(BaseModel):
    """Payload do webhook Evolution API v2"""
    event: str
    instance: str
    data: dict
    destination: Optional[str] = None
    date_time: Optional[str] = None
    sender: Optional[str] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None

    def to_whatsapp_message(self) -> WhatsAppMessage:
        """Converte para WhatsAppMessage"""
        # Extrai dados da mensagem
        key = self.data.get("key", {})
        message_data = self.data.get("message", {})

        # Extrai texto (pode estar em "conversation" ou outros campos)
        text = (
            message_data.get("conversation", "") or
            message_data.get("extendedTextMessage", {}).get("text", "") or
            message_data.get("imageMessage", {}).get("caption", "") or
            ""
        )

        # Determina tipo de mensagem
        if "conversation" in message_data or "extendedTextMessage" in message_data:
            message_type = "Conversation"
        elif "audioMessage" in message_data:
            message_type = "AudioMessage"
        elif "imageMessage" in message_data:
            message_type = "ImageMessage"
        else:
            message_type = "Conversation"

        # Prioriza o campo que NÃO termina com @lid
        remote_jid = key.get("remoteJid", "")
        remote_jid_alt = key.get("remoteJidAlt", "")

        # Se um deles termina com @lid, usa o outro
        if remote_jid.endswith("@lid") and not remote_jid_alt.endswith("@lid"):
            chat_id = remote_jid_alt
        elif remote_jid_alt.endswith("@lid") and not remote_jid.endswith("@lid"):
            chat_id = remote_jid
        else:
            # Se ambos ou nenhum terminam com @lid, prioriza remoteJid
            chat_id = remote_jid or remote_jid_alt

        return WhatsAppMessage(
            chatid=chat_id,
            sender=chat_id,
            sender_name=self.data.get("pushName", ""),
            text=text,
            message_type=message_type,
            message_id=key.get("id", ""),
            timestamp=self.data.get("messageTimestamp", 0),
            from_me=key.get("fromMe", False)
        )
