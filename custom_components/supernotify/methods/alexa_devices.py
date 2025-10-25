import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_MESSAGE
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACTION, CONF_DEFAULT

from custom_components.supernotify import (
    CONF_OPTIONS,
    METHOD_ALEXA,
    MessageOnlyPolicy,
)
from custom_components.supernotify.delivery_method import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)
ACTION = "notify.send_message"


class AlexaDevicesDeliveryMethod(DeliveryMethod):
    """Notify via Home Assistant's built-in Alexa Devices integration

    options:
        message_usage: standard | use_title | combine_title

    """

    method = METHOD_ALEXA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DEFAULT, {})
        kwargs[CONF_DEFAULT].setdefault(CONF_ACTION, ACTION)
        kwargs[CONF_DEFAULT].setdefault(CONF_OPTIONS, {})
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_SIMPLIFY_TEXT, True)
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_STRIP_URLS, True)
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_MESSAGE_USAGE, MessageOnlyPolicy.STANDARD)
        super().__init__(*args, **kwargs)

    def select_target(self, target: str) -> bool:
        return (
            re.fullmatch(r"notify\.[a-z0-9_]+\_(speak|announce)", target) is not None
            or re.fullmatch(r"group\.[a-z0-9_]+", target) is not None
        )

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_devices: %s", envelope.message)

        targets = envelope.targets or []

        if not targets:
            _LOGGER.debug("SUPERNOTIFY skipping alexa devices, no targets")
            return False

        action_data: dict[str, Any] = {ATTR_MESSAGE: envelope.message or ""}
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}

        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
