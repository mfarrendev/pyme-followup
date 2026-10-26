"""Envío de correo. El trabajador no sabe si es SMTP o captura: recibe un Enviador."""

import smtplib
import sqlite3
import ssl
from email.message import EmailMessage

from app.config import ajustes
from app.reloj import Reloj, iso


class ErrorTransitorio(Exception):
    """Se puede reintentar: el servidor no respondió, rechazó por carga, etc."""


class ErrorPermanente(Exception):
    """Reintentar no sirve: credenciales inválidas, dirección rechazada. Requiere intervención."""


class ResultadoAmbiguo(Exception):
    """El servidor pudo haber aceptado el mensaje y se perdió la confirmación.

    Reintentar a ciegas podría mandar el correo dos veces; se marca para revisión.
    """


class Enviador:
    def enviar(self, para: str, asunto: str, cuerpo: str) -> str | None:
        """Envía y devuelve el id del proveedor si lo hay."""
        raise NotImplementedError


class EnviadorMemoria(Enviador):
    """Captura los correos en la base: para la demo y las pruebas."""

    def __init__(self, con: sqlite3.Connection, reloj: Reloj):
        self.con, self.reloj = con, reloj

    def enviar(self, para: str, asunto: str, cuerpo: str) -> str | None:
        cur = self.con.execute(
            "INSERT INTO correos_capturados (para, asunto, cuerpo, fecha) VALUES (?, ?, ?, ?)",
            (para, asunto, cuerpo, iso(self.reloj.ahora())),
        )
        return f"captura-{cur.lastrowid}"


class EnviadorSMTP(Enviador):
    def enviar(self, para: str, asunto: str, cuerpo: str) -> str | None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = ajustes.correo_remitente, para, asunto
        msg.set_content(cuerpo)
        try:
            with smtplib.SMTP(ajustes.smtp_host, ajustes.smtp_puerto, timeout=20) as smtp:
                if ajustes.smtp_tls:
                    smtp.starttls(context=ssl.create_default_context())
                if ajustes.smtp_usuario:
                    smtp.login(ajustes.smtp_usuario, ajustes.smtp_clave)
                smtp.send_message(msg)
        except (
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
        ) as e:
            raise ErrorPermanente(type(e).__name__) from e
        except smtplib.SMTPServerDisconnected as e:
            # Se cortó después de enviar los datos: no se sabe si quedó aceptado.
            raise ResultadoAmbiguo(type(e).__name__) from e
        except (smtplib.SMTPException, OSError) as e:
            raise ErrorTransitorio(type(e).__name__) from e
        return msg.get("Message-ID")
