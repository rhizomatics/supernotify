from __future__ import annotations

import datetime as dt
import email.utils
import logging
import os.path
import smtplib
import time
from contextlib import suppress
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from traceback import format_exception
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.components.smtp.const import CONF_SENDER_NAME, CONF_SERVER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SENDER, CONF_TIMEOUT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import create_client_context

from custom_components.supernotify import const
from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.const import (
    CONF_CONNECTION,
    CONF_DELIVERY_DEFAULTS,
    CONF_ENCRYPTION,
    CONF_OPTIONS,
    OPTION_DEFAULT_TITLE,
    OPTION_SENDER,
    OPTION_SENDER_NAME,
    TRANSPORT_SMTP,
)
from custom_components.supernotify.model import (
    DeliveryConfig,
    SuppressionReason,
    TransportConfig,
)
from custom_components.supernotify.transports.email import EmailTransport

if TYPE_CHECKING:
    from ssl import SSLContext

    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.context import Context
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 587
DEFAULT_ENCRYPTION = "starttls"
DEFAULT_TIMEOUT = 5
NULL_RETURN_PATH = "<>"

# Keys used in the HA core smtp integration's config entry data, for reuse when no
# connection is configured here. "server" is smtp-specific; the rest match generic
# homeassistant.const keys already imported above.
HA_SMTP_DOMAIN = "smtp"

IMPORTANCE_HEADER_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "high",
    const.PRIORITY_HIGH: "high",
    const.PRIORITY_MEDIUM: "normal",
    const.PRIORITY_LOW: "low",
    const.PRIORITY_MINIMUM: "low",
}
PRIORITY_HEADER_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "urgent",
    const.PRIORITY_HIGH: "urgent",
    const.PRIORITY_MEDIUM: "normal",
    const.PRIORITY_LOW: "non-urgent",
    const.PRIORITY_MINIMUM: "non-urgent",
}
X_MSMAIL_PRIORITY_HEADER_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "High",
    const.PRIORITY_HIGH: "High",
    const.PRIORITY_MEDIUM: "Normal",
    const.PRIORITY_LOW: "Low",
    const.PRIORITY_MINIMUM: "Low",
}
X_PRIORITY_HEADER_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "1",
    const.PRIORITY_HIGH: "2",
    const.PRIORITY_MEDIUM: "3",
    const.PRIORITY_LOW: "4",
    const.PRIORITY_MINIMUM: "5",
}


class SmtpTransport(EmailTransport):
    """Email transport that sends via its own SMTP connection.

    Unlike the `email` transport, which calls an HA notify action, this owns the SMTP
    connection directly so it can send to arbitrary addresses without every recipient
    needing to be pre-registered as a notify entity (as HA's own smtp integration now
    requires), and so it isn't limited to whatever a given HA notify action exposes.
    Reuses EmailTransport's template rendering/image handling and only replaces the
    final delivery step.

    If no `connection` is configured, falls back to reusing the host/port/encryption/
    credentials/sender from HA's own smtp integration config entry, if one exists.
    """

    name = TRANSPORT_SMTP

    def __init__(self, context: Context, transport_config: ConfigType | None = None) -> None:
        super().__init__(context, transport_config)
        connection: ConfigType = (transport_config or {}).get(CONF_CONNECTION, {})
        self.host: str | None = connection.get(CONF_HOST)
        self.port: int = connection.get(CONF_PORT, DEFAULT_PORT)
        self.encryption: str = connection.get(CONF_ENCRYPTION, DEFAULT_ENCRYPTION)
        self.username: str | None = connection.get(CONF_USERNAME)
        self.password: str | None = connection.get(CONF_PASSWORD)
        self.timeout: int = connection.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self.verify_ssl: bool = connection.get(CONF_VERIFY_SSL, True)
        options: dict[str, Any] = (transport_config or {}).get(CONF_DELIVERY_DEFAULTS, {}).get(CONF_OPTIONS, {})
        self.sender: str | None = options.get(OPTION_SENDER)
        self.sender_name: str | None = options.get(OPTION_SENDER_NAME)
        self.default_title: str | None = options.get(OPTION_DEFAULT_TITLE)

        if not self.host:
            self._reuse_ha_smtp_connection()

    def _reuse_ha_smtp_connection(self) -> None:
        """No connection configured here; fall back to a configured HA smtp integration entry, if any."""
        entry_data = self.hass_api.find_config_entry_data(HA_SMTP_DOMAIN)
        if not entry_data:
            _LOGGER.debug("SUPERNOTIFY no home assistant official smtp configuration to reuse")
            return
        _LOGGER.info("SUPERNOTIFY smtp transport reusing connection from HA smtp integration")
        self.host = entry_data.get(CONF_SERVER)
        self.port = entry_data.get(CONF_PORT, self.port)
        self.encryption = entry_data.get(CONF_ENCRYPTION, self.encryption)
        self.username = entry_data.get(CONF_USERNAME, self.username)
        self.password = entry_data.get(CONF_PASSWORD, self.password)
        self.verify_ssl = entry_data.get(CONF_VERIFY_SSL, self.verify_ssl)
        if not self.sender:
            self.sender = entry_data.get(CONF_SENDER)
        if not self.sender_name:
            self.sender_name = entry_data.get(CONF_SENDER_NAME)

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        if self.host and self.sender:
            return self.delivery_defaults
        return None

    @property
    def default_config(self) -> TransportConfig:
        config = super().default_config
        config.delivery_defaults.options[OPTION_SENDER_NAME] = "Home Assistant"
        config.delivery_defaults.options[OPTION_DEFAULT_TITLE] = "Home Assistant Notification"
        return config

    def validate_action(self, action: str | None) -> bool:
        """No HA action is used; instead require a usable SMTP connection."""
        return bool(self.host and self.sender)

    async def _send(self, envelope: Envelope, action_data: dict[str, Any]) -> bool:
        addresses: list[str] = action_data.get(ATTR_TARGET) or []
        start_time = time.time()
        timestamp = dt.datetime.now(tz=dt_util.get_default_time_zone())
        if not self.host or not self.sender:
            _LOGGER.debug("SUPERNOTIFY skipping smtp delivery %s, no connection configured", envelope.delivery.name)
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_ACTION
            return False
        if not addresses:
            _LOGGER.debug("SUPERNOTIFY skipping smtp delivery %s, no target addresses", envelope.delivery.name)
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_TARGET
            return False

        try:
            msg = self._build_message(action_data, addresses, envelope.priority, envelope.id)
            await self.hass_api.create_job(self._send_smtp, msg, addresses)
            envelope.calls.append(
                CallRecord(
                    timestamp,
                    time.time() - start_time,
                    domain="smtp",
                    action="send_message",
                    debug=envelope.delivery.debug,
                    action_data=dict(action_data),
                    target_data={ATTR_TARGET: addresses},
                )
            )
            envelope.delivered = 1
            return True
        except Exception as e:
            self.record_error(str(e), method="_send")
            envelope.failed_calls.append(
                CallRecord(
                    timestamp,
                    time.time() - start_time,
                    domain="smtp",
                    action="send_message",
                    action_data=dict(action_data),
                    target_data={ATTR_TARGET: addresses},
                    exception=str(e),
                )
            )
            _LOGGER.exception("SUPERNOTIFY Failed to send smtp email for %s", envelope.delivery.name)
            envelope.error_count += 1
            envelope.delivery_error = format_exception(e)
            return False

    def _build_message(
        self, action_data: dict[str, Any], addresses: list[str], priority: str | None, id: str | None
    ) -> MIMEMultipart | MIMEText:
        title: str | None = action_data.get(ATTR_TITLE)
        message: str = action_data.get(ATTR_MESSAGE) or ""
        data: dict[str, Any] = action_data.get(ATTR_DATA) or {}
        html: str | None = data.get("html")
        images: list[str] = data.get("images") or []

        msg: MIMEMultipart | MIMEText
        if html or images:
            msg = MIMEMultipart("related")
            alternative = MIMEMultipart("alternative")
            alternative.attach(MIMEText(message, _charset="utf-8"))
            if html:
                alternative.attach(MIMEText(html, "html", _charset="utf-8"))
            msg.attach(alternative)
            for image_path in images:
                attachment = self._attach_file(image_path)
                if attachment:
                    msg.attach(attachment)
        else:
            msg = MIMEText(message)

        msg["Subject"] = title or self.default_title or ""
        msg["To"] = ", ".join(addresses)
        if self.sender_name or self.sender:
            sender: str = email.utils.formataddr((self.sender_name or "", self.sender or ""))
        else:
            sender = NULL_RETURN_PATH

        msg["From"] = sender
        msg["X-Mailer"] = "Home Assistant Supernotify"
        msg["Date"] = email.utils.format_datetime(dt_util.now())
        msg["Message-Id"] = email.utils.make_msgid(idstring=id)
        if priority:
            msg["Importance"] = IMPORTANCE_HEADER_MAP.get(priority, "Normal")
            msg["Priority"] = PRIORITY_HEADER_MAP.get(priority, "normal")
            msg["X-Priority"] = X_PRIORITY_HEADER_MAP.get(priority, "3")
            msg["X-MSMail-Priority"] = X_MSMAIL_PRIORITY_HEADER_MAP.get(priority, "Normal")
        return msg

    def _attach_file(self, image_path: str) -> MIMEImage | MIMEApplication | None:
        try:
            with open(image_path, "rb") as attachment_file:
                file_bytes = attachment_file.read()
        except OSError:
            _LOGGER.warning("SUPERNOTIFY smtp attachment %s not found, skipping", image_path)
            return None

        content_id: str = os.path.basename(image_path)
        attachment: MIMEImage | MIMEApplication
        try:
            attachment = MIMEImage(file_bytes)
        except TypeError:
            attachment = MIMEApplication(file_bytes, Name=content_id)
            attachment["Content-Disposition"] = f'attachment; filename="{content_id}"'
        attachment.add_header("Content-ID", f"<{content_id}>")
        return attachment

    def _send_smtp(self, msg: MIMEMultipart | MIMEText, addresses: list[str]) -> None:
        if not self.host or not self.port:
            _LOGGER.warning("SUPERNOTIFY smtp integration not configured")
            return

        ssl_context: SSLContext | None = create_client_context() if self.verify_ssl else None
        client: smtplib.SMTP | smtplib.SMTP_SSL
        if self.encryption == "tls":
            client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ssl_context)
        else:
            client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        try:
            client.ehlo_or_helo_if_needed()
            if self.encryption == "starttls":
                client.starttls(context=ssl_context)
                client.ehlo()
            if self.username and self.password:
                client.login(self.username, self.password)
            client.sendmail(self.sender or NULL_RETURN_PATH, addresses, msg.as_string())
        finally:
            with suppress(smtplib.SMTPException):
                client.quit()
