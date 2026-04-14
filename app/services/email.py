"""
Serviço de envio de email via SMTP (Gmail)
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Serviço de envio de email via SMTP"""

    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.user = settings.smtp_user
        self.password = settings.smtp_password
        self.from_name = settings.smtp_from_name

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """
        Envia um email.

        Args:
            to: Email destinatário
            subject: Assunto do email
            body: Corpo do email (texto)

        Returns:
            True se enviado com sucesso
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.user}>"
            msg["To"] = to

            # Versão texto puro
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # Versão HTML — converte quebras de linha e negrito do WhatsApp
            html_body = self._to_html(body)
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, to, msg.as_string())

            logger.info(f"[EMAIL] Email enviado para {to} - assunto: {subject}")
            return True

        except Exception as e:
            logger.error(f"[EMAIL] Erro ao enviar email para {to}: {e}")
            return False

    def _to_html(self, text: str) -> str:
        """Converte texto com formatação WhatsApp (*negrito*) para HTML."""
        import re
        # Escapa HTML básico
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # *negrito* → <strong>
        text = re.sub(r"\*(.+?)\*", r"<strong>\1</strong>", text)
        # Quebras de linha
        text = text.replace("\n", "<br>")
        return f"""
        <html><body style="font-family: Arial, sans-serif; font-size: 14px; color: #333; max-width: 700px; margin: auto; padding: 20px;">
            <div style="background:#f5f5f5; border-left: 4px solid #2e7d32; padding: 16px; border-radius: 4px;">
                {text}
            </div>
            <p style="color:#999; font-size:12px; margin-top:20px;">
                Este é um relatório automático gerado pela Comexim IA.<br>
                Para cancelar, envie uma mensagem no WhatsApp.
            </p>
        </body></html>
        """


# Instância global
email_service = EmailService()
