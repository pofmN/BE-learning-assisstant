from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi import BackgroundTasks
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Any
from pydantic import NameEmail, SecretStr
from app.core.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

mail_conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=SecretStr(settings.MAIL_PASSWORD),
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.USE_CREDENTIALS,
    VALIDATE_CERTS=settings.VALIDATE_CERTS
)


class MailService:
    def __init__(self, conf: ConnectionConfig = mail_conf):
        self._conf = conf
        self._fm = FastMail(conf)

    async def send_message_background(self, background_tasks: BackgroundTasks, subject: str, recipients: list[NameEmail], template_name: str, context: dict[str, Any]):
        template = jinja_env.get_template(template_name)
        html = template.render(**context)
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=html,
            subtype=MessageType.html
        )
        # FastMail.send_message is async; run in background
        background_tasks.add_task(self._fm.send_message, message)
