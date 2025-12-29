import logging
import os
from pathlib import Path
from typing import Any, TypedDict

import aiofiles
from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify import (
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_EMAIL,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    CONF_TEMPLATE,
    OPTION_JPEG,
    OPTION_MESSAGE_USAGE,
    OPTION_PNG,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRICT_TEMPLATE,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import DebugTrace, DeliveryConfig, MessageOnlyPolicy, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

RE_VALID_EMAIL = (
    r"^[a-zA-Z0-9.+/=?^_-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)
OPTION_PREHEADER_BLANK = "preheader_blank"
OPTION_PREHEADER_LENGTH = "preheader_length"

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
        self.template_path: Path | None = None
        if context.template_path:
            self.template_path = context.template_path / "email"
            if not self.template_path.exists():
                _LOGGER.warning("SUPERNOTIFY Email templates not available at %s", self.template_path)
                self.template_path = None
            else:
                _LOGGER.debug("SUPERNOTIFY Loading email templates from %s", self.template_path)
        else:
            _LOGGER.warning("SUPERNOTIFY Email templates not available - no configured path")

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is not None

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        action: str | None = hass_api.find_service("notify", "homeassistant.components.smtp.notify")
        if action:
            delivery_config = self.delivery_defaults
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
        )

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
        }
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_email: %s %s", envelope.delivery_name, envelope.target.email)

        data: dict[str, Any] = envelope.data or {}
        html: str | None = data.get("html")
        template: str | None = data.get(CONF_TEMPLATE, envelope.delivery.template)
        strict_template: bool = envelope.delivery.options.get(OPTION_STRICT_TEMPLATE, False)
        addresses: list[str] = envelope.target.email or []
        snapshot_url: str | None = data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is None:
            # older location for backward compatibility
            snapshot_url = data.get(ATTR_MEDIA_SNAPSHOT_URL)
        # TODO: centralize in config
        footer_template = data.get("footer")
        footer = footer_template.format(e=envelope) if footer_template else None

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

        if not template or not self.template_path:
            if footer and action_data.get(ATTR_MESSAGE):
                action_data[ATTR_MESSAGE] = f"{action_data[ATTR_MESSAGE]}\n\n{footer}"

            if envelope.message_html:
                action_data.setdefault("data", {})
                html = envelope.message_html
                if image_path:
                    image_name = image_path.name
                    if html and "cid:%s" not in html and not html.endswith("</html"):
                        if snapshot_url:
                            html += f'<div><p><a href="{snapshot_url}">'
                            html += f'<img src="cid:{image_name}"/></a>'
                            html += "</p></div>"
                        else:
                            html += f'<div><p><img src="cid:{image_name}"></p></div>'

                action_data["data"]["html"] = html
        else:
            html = await self.render_template(
                template,
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
        return await self.call_action(envelope, action_data=action_data)

    async def render_template(
        self,
        template: str,
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
        if self.template_path is None:
            _LOGGER.error("SUPERNOTIFY No template path set")
            return None
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

            template_file_path = self.template_path / template
            template_content: str
            async with aiofiles.open(template_file_path) as file:
                template_content = os.linesep.join(await file.readlines())
            template_obj: Template = self.context.hass_api.template(template_content)
            template_obj.ensure_valid()

            if debug_trace:
                debug_trace.record_delivery_artefact(envelope.delivery.name, "alert", alert)

            html: str = template_obj.async_render(variables={"alert": alert}, parse_result=False, strict=strict_template)
            if not html:
                _LOGGER.error("SUPERNOTIFY Empty result from template %s", template_file_path)
            else:
                return html
        except TemplateError as te:
            _LOGGER.error("SUPERNOTIFY Failed to render template html mail: %s", te)
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to generate html mail: %s", e)
        return None

    def pack_preheader(self, preheader: str, options: dict[str, Any]) -> str:
        phchars: str = options.get(OPTION_PREHEADER_BLANK, "")
        phlength: int = options.get(OPTION_PREHEADER_LENGTH, 0)
        if phlength and phchars:
            return f"{preheader}{phchars * (phlength - len(preheader))}"
        return preheader
