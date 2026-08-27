from __future__ import annotations

import datetime as dt
import email.utils
import logging
import os
import os.path
import smtplib
import time
from contextlib import suppress
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from traceback import format_exception
from typing import TYPE_CHECKING, Any, TypedDict

import aiofiles
from anyio import Path
from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.components.smtp.const import CONF_SENDER_NAME, CONF_SERVER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SENDER, CONF_TIMEOUT, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.util import dt as dt_util
from homeassistant.util.ssl import create_client_context

import custom_components.supernotify
from custom_components.supernotify import const
from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.const import (
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_EMAIL,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    CONF_CONNECTION,
    CONF_DELIVERY_DEFAULTS,
    CONF_ENCRYPTION,
    CONF_OPTIONS,
    CONF_TEMPLATE,
    EMAIL_OPTION_MODE_DIRECT,
    EMAIL_OPTION_MODE_HA_SMTP,
    OPTION_DEFAULT_TITLE,
    OPTION_JPEG,
    OPTION_MESSAGE_USAGE,
    OPTION_MODE,
    OPTION_PNG,
    OPTION_SENDER,
    OPTION_SENDER_NAME,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRICT_TEMPLATE,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.model import (
    DebugTrace,
    DeliveryConfig,
    MessageOnlyPolicy,
    SuppressionReason,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from ssl import SSLContext

    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.context import Context
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

RE_VALID_EMAIL = (
    r"^[a-zA-Z0-9.+/=?^_-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
OPTION_PREHEADER_BLANK = "preheader_blank"
OPTION_PREHEADER_LENGTH = "preheader_length"

DEFAULT_SMTP_PORT = 587
DEFAULT_SMTP_ENCRYPTION = "starttls"
DEFAULT_SMTP_TIMEOUT = 5
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

_LOGGER = logging.getLogger(__name__)


class AlertServer(TypedDict):
    name: str
    internal_url: str
    external_url: str
    language: str


class AlertImage(TypedDict):
    url: str
    desc: str


class Alert(TypedDict):
    message: str | None
    title: str | None
    preheader: str | None
    priority: str
    envelope: Envelope
    action_url: str | None
    action_url_title: str | None
    subheading: str
    server: AlertServer
    preformatted_html: str | None
    img: AlertImage | None


class EmailTransport(Transport):
    name = TRANSPORT_EMAIL

    def __init__(self, context: Context, transport_config: ConfigType | None = None) -> None:
        super().__init__(context, transport_config)
        self.default_template_path: Path = Path(os.path.join(custom_components.supernotify.__path__[0], "default_templates"))
        self.custom_template_path: Path | None = context.custom_template_path
        self.custom_email_template_path: Path | None = None
        self.template_cache: dict[str, str] = {}

        # Connection details for sending via a direct SMTP connection - only used for
        # deliveries with the OPTION_MODE option set to direct, rather than the default of
        # calling an HA notify action, but always read here since a delivery can request
        # direct sending independently of how this transport itself was configured.
        connection: ConfigType = (transport_config or {}).get(CONF_CONNECTION, {})
        self.host: str | None = connection.get(CONF_HOST)
        self.port: int = connection.get(CONF_PORT, DEFAULT_SMTP_PORT)
        self.encryption: str = connection.get(CONF_ENCRYPTION, DEFAULT_SMTP_ENCRYPTION)
        self.username: str | None = connection.get(CONF_USERNAME)
        self.password: str | None = connection.get(CONF_PASSWORD)
        self.timeout: int = connection.get(CONF_TIMEOUT, DEFAULT_SMTP_TIMEOUT)
        self.verify_ssl: bool = connection.get(CONF_VERIFY_SSL, True)
        options: dict[str, Any] = (transport_config or {}).get(CONF_DELIVERY_DEFAULTS, {}).get(CONF_OPTIONS, {})
        self.sender: str | None = options.get(OPTION_SENDER)
        self.sender_name: str | None = options.get(OPTION_SENDER_NAME)
        self.default_title: str | None = options.get(OPTION_DEFAULT_TITLE)

        if not self.host:
            self._reuse_ha_smtp_connection()

    def _reuse_ha_smtp_connection(self) -> None:
        """No direct SMTP connection configured here; fall back to a configured HA smtp
        integration entry, if any."""
        entry_data = self.hass_api.find_config_entry_data(HA_SMTP_DOMAIN)
        if not entry_data:
            _LOGGER.debug("SUPERNOTIFY No home assistant official smtp configuration to reuse")
            return
        _LOGGER.info("SUPERNOTIFY Email transport reusing connection from HA smtp integration for direct SMTP sends")
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

    async def initialize(self) -> None:
        try:
            if self.custom_template_path is not None:
                if await self.custom_template_path.exists():
                    if await (self.custom_template_path / "email").exists():
                        _LOGGER.debug("SUPERNOTIFY Using email specific custom templates at %s", self.custom_template_path)
                        self.custom_email_template_path = Path(self.custom_template_path / "email")
                    else:
                        _LOGGER.debug("SUPERNOTIFY Email specific custom templates not configured")
                else:
                    _LOGGER.info("SUPERNOTIFY Custom email template directory not present at %s", self.custom_template_path)
                    self.custom_template_path = None
            else:
                _LOGGER.info("SUPERNOTIFY Custom email templates not configured")
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Failed to verify custom template path %s: %s", self.custom_template_path, e)

    def validate_action(self, action: str | None) -> bool:
        """Valid either with an HA notify action, or a usable direct SMTP connection for
        deliveries that set OPTION_MODE to 'direct'."""
        return action is not None or bool(self.host and self.sender)

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        action: str | None = hass_api.find_service("notify", "homeassistant.components.smtp.notify")
        if action:
            delivery_config: DeliveryConfig = self.delivery_defaults
            delivery_config.action = action
            return delivery_config
        return None

    @property
    def supported_features(self) -> TransportFeature:
        return (
            TransportFeature.MESSAGE
            | TransportFeature.TITLE
            | TransportFeature.ACTIONS
            | TransportFeature.IMAGES
            | TransportFeature.TEMPLATE_FILE
            | TransportFeature.SNAPSHOT_IMAGE
        )

    def extra_attributes(self) -> dict[str, Any]:
        return {
            "cached_templates": list(self.template_cache.keys()),
            "custom_templates": str(self.custom_template_path) if self.custom_template_path else None,
            "custom_email_templates": str(self.custom_email_template_path) if self.custom_email_template_path else None,
        }

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_EMAIL],
            # use sensible defaults for image attachments
            OPTION_JPEG: {"progressive": "true", "optimize": "true"},
            OPTION_PNG: {"optimize": "true"},
            OPTION_STRICT_TEMPLATE: False,
            OPTION_PREHEADER_BLANK: "&#847;&zwnj;&nbsp;",
            OPTION_PREHEADER_LENGTH: 100,
            # only used for deliveries with OPTION_MODE set to 'direct'
            OPTION_SENDER_NAME: "Home Assistant",
            OPTION_DEFAULT_TITLE: "Home Assistant Notification",
        }
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_email: %s %s", envelope.delivery_name, envelope.target.email)

        data: dict[str, Any] = envelope.data or {}
        html: str | None = data.get("html")
        template_name: str | None = data.get(CONF_TEMPLATE, envelope.delivery.template)
        strict_template: bool = envelope.delivery.options.get(OPTION_STRICT_TEMPLATE, False)
        addresses: list[str] = envelope.target.email or []
        snapshot_url: str | None = data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is None:
            # older location for backward compatibility
            snapshot_url = data.get(ATTR_MEDIA_SNAPSHOT_URL)
        # TODO: centralize in config
        footer_template = data.get("footer")
        footer = None
        if footer_template:
            try:
                footer = footer_template.format(e=envelope)
            except (KeyError, ValueError, AttributeError) as ex:  # py3.13 compat
                _LOGGER.warning("SUPERNOTIFY email: failed to render footer template: %s", ex)

        action_data: dict[str, Any] = envelope.core_action_data()
        extra_data: dict[str, Any] = {k: v for k, v in data.items() if k not in action_data}

        if len(addresses) > 0:
            action_data[ATTR_TARGET] = addresses
            # default to SMTP platform default recipients if no explicit addresses

        if data and data.get("data"):
            action_data[ATTR_DATA] = data.get("data")

        image_path: Path | None = await envelope.grab_image()
        if image_path:
            action_data.setdefault("data", {})
            action_data["data"]["images"] = [str(image_path)]

        if not template_name:
            if footer and action_data.get(ATTR_MESSAGE):
                action_data[ATTR_MESSAGE] = f"{action_data[ATTR_MESSAGE]}\n\n{footer}"

            if envelope.message_html:
                action_data.setdefault("data", {})
                html = envelope.message_html
                if image_path:
                    image_name = image_path.name
                    if html and not html.rstrip().endswith("</html>"):
                        if snapshot_url:
                            html += f'<div><p><a href="{snapshot_url}">'
                            html += f'<img src="cid:{image_name}"/></a>'
                            html += "</p></div>"
                        else:
                            html += f'<div><p><img src="cid:{image_name}"></p></div>'

                action_data["data"]["html"] = html
        else:
            html = await self.render_template(
                template_name,
                envelope,
                action_data,
                debug_trace,
                image_path=image_path,
                snapshot_url=snapshot_url,
                extra_data=extra_data,
                strict_template=strict_template,
            )
            if html:
                action_data.setdefault("data", {})
                action_data["data"]["html"] = html
        return await self._send(envelope, action_data)

    async def _send(self, envelope: Envelope, action_data: dict[str, Any]) -> bool:
        """Send the built action_data, either via an HA notify action, or by owning the SMTP
        connection directly - for deliveries with the OPTION_MODE option set, so
        email can be sent to arbitrary addresses without every recipient needing to be
        pre-registered as a notify entity, and isn't limited to whatever a given HA notify
        action exposes."""
        if envelope.delivery.options.get(OPTION_MODE, EMAIL_OPTION_MODE_HA_SMTP) == EMAIL_OPTION_MODE_DIRECT:
            return await self._send_direct_smtp(envelope, action_data)
        return await self.call_action(envelope, action_data=action_data)

    async def _send_direct_smtp(self, envelope: Envelope, action_data: dict[str, Any]) -> bool:
        addresses: list[str] = action_data.get(ATTR_TARGET) or []
        start_time = time.time()
        timestamp = dt.datetime.now(tz=dt_util.get_default_time_zone())
        if not self.host or not self.sender:
            _LOGGER.debug("SUPERNOTIFY Skipping direct smtp delivery %s, no connection configured", envelope.delivery.name)
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_ACTION
            return False
        if not addresses:
            _LOGGER.debug("SUPERNOTIFY Skipping direct smtp delivery %s, no target addresses", envelope.delivery.name)
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_TARGET
            return False

        try:
            msg = await self._build_message(action_data, addresses, envelope.priority, envelope.id)
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
            self.log_delivery_recovered()
            return True
        except Exception as e:
            self.record_error(str(e), method="_send_direct_smtp")
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
            self.log_delivery_failure(e, "SUPERNOTIFY Failed to send smtp email for %s", envelope.delivery.name)
            envelope.error_count += 1
            envelope.delivery_error = format_exception(e)
            return False

    async def _build_message(
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
                attachment = await self._attach_file(image_path)
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

    async def _attach_file(self, image_path: str) -> MIMEImage | MIMEApplication | None:
        try:
            async with aiofiles.open(image_path, "rb") as attachment_file:
                file_bytes = await attachment_file.read()
        except OSError:
            _LOGGER.warning("SUPERNOTIFY SMTP attachment %s not found, skipping", image_path)
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
            _LOGGER.warning("SUPERNOTIFY Direct SMTP connection not configured")
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

    async def load_template(self, template_name: str) -> str | None:
        if template_name in self.template_cache:
            return self.template_cache[template_name]

        for root_path in (
            self.custom_email_template_path,
            self.custom_template_path,
            self.default_template_path / "email",
            self.default_template_path,
        ):
            if root_path is not None:
                template_path: Path = root_path / template_name
                if await template_path.exists():
                    template: str
                    async with aiofiles.open(template_path) as file:
                        template = os.linesep.join(await file.readlines())
                        self.template_cache[template_name] = template
                        return template
        return None

    async def render_template(
        self,
        template_name: str,
        envelope: Envelope,
        action_data: dict[str, Any],
        debug_trace: DebugTrace | None = None,
        image_path: Path | None = None,
        snapshot_url: str | None = None,
        extra_data: dict[str, Any] | None = None,
        strict_template: bool = False,
    ) -> str | None:
        extra_data = extra_data or {}
        alert: Alert

        try:
            title: str | None = action_data.get(ATTR_TITLE)
            message: str | None = action_data.get(ATTR_MESSAGE)
            preheader: str = f"{title or ''}{' ' if title else ''}{message}"
            preheader = preheader or "Home Assistant Notification"
            alert = Alert(
                message=message,
                title=title,
                preheader=self.pack_preheader(preheader, envelope.delivery.options),
                priority=envelope.priority,
                action_url=extra_data.get(ATTR_ACTION_URL),
                action_url_title=extra_data.get(ATTR_ACTION_URL_TITLE),
                envelope=envelope,
                subheading="Home Assistant Notification",
                server=AlertServer(
                    name=self.hass_api.hass_name,
                    internal_url=self.hass_api.internal_url,
                    external_url=self.hass_api.external_url,
                    language=self.hass_api.language,
                ),
                preformatted_html=envelope.message_html,
                img=None,
            )

            if snapshot_url:
                alert["img"] = AlertImage(url=snapshot_url, desc="Snapshot Image")
            elif image_path:
                alert["img"] = AlertImage(url=f"cid:{image_path.name}", desc=image_path.name)

            template_content: str | None = await self.load_template(template_name)

            if template_content is None:
                _LOGGER.error("SUPERNOTIFY No template found for %s", template_name)
                return None

            template_obj: Template = self.context.hass_api.template(template_content)
            template_obj.ensure_valid()

            if debug_trace:
                debug_trace.record_delivery_artefact(envelope.delivery.name, "alert", alert)

            html: str = template_obj.async_render(variables={"alert": alert}, parse_result=False, strict=strict_template)
            if not html:
                _LOGGER.error("SUPERNOTIFY Empty result from template %s", template_name)
            else:
                return html
        except TemplateError as te:
            _LOGGER.exception("SUPERNOTIFY Failed to render template html mail")
            if debug_trace:
                debug_trace.record_delivery_exception(envelope.delivery.name, "html_template", te)
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to generate html mail")
            if debug_trace:
                debug_trace.record_delivery_exception(envelope.delivery.name, "html_template", e)
        return None

    def pack_preheader(self, preheader: str, options: dict[str, Any]) -> str:
        preheader = preheader or ""
        phchars: str = options.get(OPTION_PREHEADER_BLANK, "")
        phlength: int = options.get(OPTION_PREHEADER_LENGTH, 0)
        if phlength and phchars:
            return f"{preheader}{phchars * (phlength - len(preheader))}"
        return preheader
