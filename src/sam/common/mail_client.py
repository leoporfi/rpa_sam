# SAM/src/common/mail_client.py
import datetime
import logging
import smtplib
import sys  # Para sys.stderr y sys.path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

from .config_manager import ConfigManager

# --- OBTENER EL LOGGER (Forma Estandarizada) ---
# Simplemente obtenemos el logger para este módulo. La configuración
# (handlers, level, etc.) ya fue establecida por el script de arranque.
logger = logging.getLogger(__name__)


class EmailAlertClient:
    def __init__(self, service_name: str = "SAM"):
        # ConfigManager se importa desde common.utils.config_manager
        config = ConfigManager.get_email_config()

        self.smtp_server = config["smtp_server"]
        self.smtp_port = config["smtp_port"]
        self.smtp_user = config.get("smtp_user", None)
        self.smtp_password = config.get("smtp_password", None)
        self.from_email = config["from_email"]
        self.recipients = config["recipients"]
        self.use_tls = config["use_tls"]
        self.service_name = service_name
        # Validar configuración esencial para email
        if not all([self.smtp_server, self.from_email, self.recipients]):
            logger.error(
                "Configuración de email incompleta (falta smtp_server, from_email o recipients). Las alertas por email podrían no funcionar."
            )
            # Podrías levantar un error aquí si el email es crítico
            # raise ValueError("Configuración de email incompleta.")

        self.last_critical_sent: Dict[str, datetime.datetime] = {}

    def send_alert(self, subject: str, message: str, is_critical: bool = True):
        # Verificar si la configuración esencial está presente antes de intentar enviar
        if not all([self.smtp_server, self.from_email, self.recipients]):
            logger.error(f"No se puede enviar alerta (Asunto: {subject}) porque la configuración de email está incompleta.")
            return False

        try:
            now = datetime.datetime.now()

            if is_critical:
                last_sent = self.last_critical_sent.get(subject)
                # Esperar 30 minutos (1800 segundos) entre alertas críticas idénticas
                if last_sent and (now - last_sent).total_seconds() < 1800:
                    logger.warning(f"Alerta crítica omitida (enviada hace menos de 30 min): {subject}")
                    return False
                self.last_critical_sent[subject] = now

            msg = MIMEMultipart()
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.recipients)  # Convertir lista a string para el header
            prefix = "[CRÍTICO]" if is_critical else "[ALERTA]"
            msg["Subject"] = f"{self.service_name} {prefix} {subject}"  # Añadir identificador del servicio

            # Usar preformateado para el cuerpo del mensaje si es texto plano, o asegurar que el HTML sea seguro.
            body_html = f"""
            <html>
            <head></head>
            <body>
                <p><b>Servicio:</b> {self.service_name}</p>
                <p><b>Asunto:</b> {subject}</p>
                <hr>
                <pre style="font-family: Consolas, 'Courier New', monospace; white-space: pre-wrap;">{message}</pre>
                <hr>
                <p><small>Este es un mensaje generado automáticamente.</small></p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body_html, "html", "utf-8"))  # Especificar utf-8

            server: Optional[smtplib.SMTP] = None  # Para asegurar que server se define
            # Añadir timeout
            timeout = 10
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=timeout)  # Añadir timeout
                server.starttls()
            else:
                if str(self.smtp_port) == "465":
                    server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=timeout)
                else:
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=timeout)

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
                logger.info("SMTP login realizado.")
            else:
                logger.info("SMTP sin autenticación (no se proporcionaron credenciales).")

            server.send_message(msg)
            server.quit()
            logger.info(f"Alerta enviada exitosamente: {subject}")
            return True

        except Exception as e:
            logger.error(f"Error al enviar alerta (Asunto: {subject}): {e}", exc_info=True)
            return False
