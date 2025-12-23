import logging
from typing import TYPE_CHECKING, Any

import aiofiles
from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify import (
    ATTR_EMAIL,
    CONF_TEMPLATE,
    OPTION_JPEG,
    OPTION_MESSAGE_USAGE,
    OPTION_PNG,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, TransportConfig, TransportFeature
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from pathlib import Path


RE_VALID_EMAIL = (
    r"^[a-zA-Z0-9.+/=?^_-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

_LOGGER = logging.getLogger(__name__)


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

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.ACTIONS \
             | TransportFeature.IMAGES | TransportFeature.TEMPLATE_FILE

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
        }
        return config

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_email: %s %s", envelope.delivery_name, envelope.target.email)

        data: dict[str, Any] = envelope.data or {}
        html: str | None = data.get("html")
        template: str | None = data.get(CONF_TEMPLATE, envelope.delivery.template)
        addresses: list[str] = envelope.target.email or []
        snapshot_url: str | None = data.get("snapshot_url")
        # TODO: centralize in config
        footer_template = data.get("footer")
        footer = footer_template.format(e=envelope) if footer_template else None

        action_data: dict[str, Any] = envelope.core_action_data()

        if len(addresses) > 0:
            action_data[ATTR_TARGET] = addresses
            # default to SMTP platform default recipients if no explicit addresses

        if data and data.get("data"):
            action_data[ATTR_DATA] = data.get("data")

        if not template or not self.template_path:
            if footer and action_data.get(ATTR_MESSAGE):
                action_data[ATTR_MESSAGE] = f"{action_data[ATTR_MESSAGE]}\n\n{footer}"

            image_path: Path | None = await envelope.grab_image()
            if image_path:
                action_data.setdefault("data", {})
                action_data["data"]["images"] = [str(image_path)]
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
            html = await self.render_template(template, envelope, action_data, snapshot_url, envelope.message_html)
            if html:
                action_data.setdefault("data", {})
                action_data["data"]["html"] = html
        return await self.call_action(envelope, action_data=action_data)

    async def render_template(
        self,
        template: str,
        envelope: Envelope,
        action_data: dict[str, Any],
        snapshot_url: str | None,
        preformatted_html: str | None,
    ) -> str | None:
        alert = {}
        if self.template_path is None:
            _LOGGER.error("SUPERNOTIFY No template path set")
            return None
        try:
            alert = {
                "alert": {
                    "message": action_data.get(ATTR_MESSAGE),
                    "title": action_data.get(ATTR_TITLE),
                    "envelope": envelope,
                    "subheading": "Home Assistant Notification",
                    "server": {
                        "name": self.hass_api.hass_name,
                        "internal_url": self.hass_api.internal_url,
                        "external_url": self.hass_api.external_url,
                    },
                    "preformatted_html": preformatted_html,
                    "img": None,
                }
            }
            if snapshot_url:
                alert["img"] = {"text": "Snapshot Image", "url": snapshot_url}

            template_file_path = self.template_path / template
            template_content: str
            async with aiofiles.open(template_file_path) as file:
                template_content = "\n".join(await file.readlines())
            template_obj: Template = self.context.hass_api.template(template_content)
            html: str = template_obj.async_render(variables=alert)
            if not html:
                _LOGGER.error("SUPERNOTIFY Empty result from template %s", template)
            else:
                return html
        except TemplateError as te:
            _LOGGER.error("SUPERNOTIFY Failed to render template html mail: %s", te)
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to generate html mail: %s", e)
        return None
