"""Agent-owned SMTP email sending tool."""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage

from clawcore.tooling import BaseTool, ToolExecutionContext
from common.observability import logger


class SendEmailTool(BaseTool):
    """Send an email via SMTP using environment-provided credentials."""

    name = "send_email"
    description = (
        "Send an email via SMTP. "
        "Payload: {to:string|list, subject:string, body:string, cc?:list, bcc?:list}."
    )

    async def execute(self, payload: dict[str, object], context: ToolExecutionContext) -> str:
        recipients = self._normalize_recipients(payload.get("to"))
        if not recipients:
            raise ValueError("send_email requires a non-empty 'to'.")

        subject = str(payload.get("subject", "")).strip()
        if not subject:
            raise ValueError("send_email requires a non-empty 'subject'.")

        body = str(payload.get("body", "")).strip()
        if not body:
            raise ValueError("send_email requires a non-empty 'body'.")

        config = self._load_config()
        cc = self._normalize_recipients(payload.get("cc"))
        bcc = self._normalize_recipients(payload.get("bcc"))

        message = EmailMessage()
        message["From"] = config["from_address"]
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        if cc:
            message["Cc"] = ", ".join(cc)
        message.set_content(body)

        all_recipients = recipients + cc + bcc
        await asyncio.to_thread(self._send_message, config, message, all_recipients)
        return f"Sent email to {', '.join(all_recipients)} with subject '{subject}'"

    def _load_config(self) -> dict[str, object]:
        host = os.environ.get("SMTP_HOST", "").strip()
        username = os.environ.get("SMTP_USERNAME", "").strip()
        password = os.environ.get("SMTP_PASSWORD", "").strip()
        from_address = os.environ.get("SMTP_FROM", "").strip()
        raw_port = os.environ.get("SMTP_PORT", "").strip() or "587"
        use_tls = os.environ.get("SMTP_USE_TLS", "true").strip().lower() != "false"
        use_ssl = os.environ.get("SMTP_USE_SSL", "false").strip().lower() == "true"

        if not host or not username or not password or not from_address:
            raise ValueError(
                "SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM are required for send_email."
            )

        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("SMTP_PORT must be a valid integer.") from exc

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "from_address": from_address,
            "use_tls": use_tls,
            "use_ssl": use_ssl,
            "timeout": 20,
        }

    def _normalize_recipients(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if isinstance(value, list):
            recipients: list[str] = []
            for item in value:
                normalized = str(item).strip()
                if normalized:
                    recipients.append(normalized)
            return recipients
        raise ValueError("send_email recipients must be a string or a list of strings.")

    def _send_message(
        self,
        config: dict[str, object],
        message: EmailMessage,
        recipients: list[str],
    ) -> None:
        host = str(config["host"])
        port = int(config["port"])
        username = str(config["username"])
        password = str(config["password"])
        use_tls = bool(config["use_tls"])
        use_ssl = bool(config["use_ssl"])
        timeout = int(config["timeout"])

        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        logger.info(
            "send_email connecting host={} port={} use_ssl={} use_tls={} recipients={}",
            host,
            port,
            use_ssl,
            use_tls,
            recipients,
        )
        with smtp_class(host, port, timeout=timeout) as server:
            if not use_ssl and use_tls:
                logger.info("send_email starting TLS for host={}", host)
                server.starttls()
            logger.info("send_email logging in as user={}", username)
            server.login(username, password)
            logger.info("send_email sending message subject={} recipients={}", message["Subject"], recipients)
            server.send_message(message, to_addrs=recipients)
