import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant
from jinja2 import Environment, FileSystemLoader

from custom_components.supernotify import ATTR_EMAIL, ATTR_PERSON_ID, CONF_TEMPLATE, METHOD_EMAIL
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery_method import (
    OPTION_JPEG,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, Target
from custom_components.supernotify.people import PeopleRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from custom_components.supernotify.delivery import Delivery

RE_VALID_EMAIL = (
    r"^[a-zA-Z0-9.+/=?^_-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)

_LOGGER = logging.getLogger(__name__)


class EmailDeliveryMethod(DeliveryMethod):
    method = METHOD_EMAIL

    def __init__(self, hass: HomeAssistant, context: Context, people_registry:PeopleRegistry,
    deliveries: dict[str, Any] | None = None, **kwargs: Any) -> None:
        super().__init__(hass, context, people_registry, deliveries, **kwargs)
        self.template_path: Path | None = None
        if self.context.template_path:
            self.template_path = self.context.template_path / "email"
            if not self.template_path.exists():
                _LOGGER.warning("SUPERNOTIFY Email templates not available at %s", self.template_path)
                self.template_path = None
            else:
                _LOGGER.debug("SUPERNOTIFY Loading email templates from %s", self.template_path)
        else:
            _LOGGER.warning("SUPERNOTIFY Email templates not available - no configured path")

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if delivery method has fixed action or doesn't require one"""
        return action is not None

    @property
    def default_options(self) -> dict[str, Any]:
        return {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            # use sensible defaults for image attachments
            OPTION_JPEG: {"progressive": "true", "optimize": "true"},
        }

    @property
    def target_categories(self) -> list[str]:
        return [ATTR_EMAIL]

    def select_targets(self, target: Target) -> Target:
        return Target({"email": target.email})

    def select_target(self,category:str,  target: str) -> bool:
        return re.fullmatch(RE_VALID_EMAIL, target) is not None

    def recipient_target(self, recipient: dict[str, Any]) -> Target|None:
        email = recipient.get(CONF_EMAIL)
        return Target({"email":[email]}) if email else None

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_email: %s %s", envelope.delivery_name, envelope.target.email)

        data: dict[str, Any] = envelope.data or {}
        config: Delivery = self.delivery_config(envelope.delivery_name)
        html: str | None = data.get("html")
        template: str | None = data.get(CONF_TEMPLATE, config.template)
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
            html = self.render_template(template, envelope, action_data, snapshot_url, envelope.message_html)
            if html:
                action_data.setdefault("data", {})
                action_data["data"]["html"] = html
        return await self.call_action(envelope, action_data=action_data)

    def render_template(
        self,
        template: str,
        envelope: Envelope,
        action_data: dict[str, Any],
        snapshot_url: str | None,
        preformatted_html: str | None,
    ) -> str | None:
        alert = {}
        try:
            alert = {
                "message": action_data.get(ATTR_MESSAGE),
                "title": action_data.get(ATTR_TITLE),
                "envelope": envelope,
                "subheading": "Home Assistant Notification",
                "configuration": self.context,
                "preformatted_html": preformatted_html,
                "img": None,
            }
            if snapshot_url:
                alert["img"] = {"text": "Snapshot Image", "url": snapshot_url}
            env = Environment(loader=FileSystemLoader(self.template_path or ""), autoescape=True)
            template_obj = env.get_template(template)
            html = template_obj.render(alert=alert)
            if not html:
                _LOGGER.error("Empty result from template %s", template)
            else:
                return html
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Failed to generate html mail: %s", e)
            _LOGGER.debug("SUPERNOTIFY Template failure: %s", alert, exc_info=True)
        return None
