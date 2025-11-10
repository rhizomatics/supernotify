import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_MESSAGE
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify import TRANSPORT_ALEXA
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, Target
from custom_components.supernotify.transport import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    Transport,
)

_LOGGER = logging.getLogger(__name__)


class AlexaDevicesTransport(Transport):
    """Notify via Home Assistant's built-in Alexa Devices integration

    options:
        message_usage: standard | use_title | combine_title

    """

    name = TRANSPORT_ALEXA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_action(self) -> str:
        return "notify.send_message"

    @property
    def default_options(self) -> dict[str, Any]:
        return {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
        }

    def select_targets(self, target: Target) -> Target:
        return Target({
            "entity_id": [
                e
                for e in target.entity_ids
                if re.fullmatch(r"notify\.[a-z0-9_]+\_(speak|announce)", e) is not None
                or re.fullmatch(r"group\.[a-z0-9_]+", e) is not None
            ]
        })

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_devices: %s", envelope.message)

        targets = envelope.target.entity_ids or []

        if not targets:
            _LOGGER.debug("SUPERNOTIFY skipping alexa devices, no targets")
            return False

        action_data: dict[str, Any] = {ATTR_MESSAGE: envelope.message or ""}
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}

        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
