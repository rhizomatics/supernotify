import logging
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET

from custom_components.supernotify import (
    ATTR_PHONE,
    CONF_PHONE_NUMBER,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_SMS,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, Target, TransportConfig
from custom_components.supernotify.transport import (
    Transport,
)

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class SMSTransport(Transport):
    name = TRANSPORT_SMS
    MAX_MESSAGE_LENGTH = 158

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.COMBINE_TITLE,
            OPTION_TARGET_CATEGORIES: [ATTR_PHONE],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is not None

    def recipient_target(self, recipient: dict[str, Any]) -> Target | None:
        phone = recipient.get(CONF_PHONE_NUMBER)
        return Target({ATTR_PHONE: [phone]}) if phone else None

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_sms: %s", envelope.delivery_name)

        data: dict[str, Any] = envelope.data or {}
        mobile_numbers = envelope.target.phone or []

        if not envelope.message:
            _LOGGER.warning("SUPERNOTIFY notify_sms: No message to send")
            return False

        message: str = envelope.message or ""
        if len(message) > self.MAX_MESSAGE_LENGTH:
            _LOGGER.debug(
                "SUPERNOTIFY notify_sms: Message too long (%d characters), truncating to %d characters",
                len(message),
                self.MAX_MESSAGE_LENGTH,
            )

        action_data = {"message": message[: self.MAX_MESSAGE_LENGTH], ATTR_TARGET: mobile_numbers}
        if data and data.get("data"):
            action_data[ATTR_DATA] = data.get("data", {})

        return await self.call_action(envelope, action_data=action_data)
