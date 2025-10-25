import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET
from homeassistant.const import CONF_DEFAULT

from custom_components.supernotify import (
    CONF_OPTIONS,
    CONF_PHONE_NUMBER,
    METHOD_SMS,
    MessageOnlyPolicy,
)
from custom_components.supernotify.delivery_method import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class SMSDeliveryMethod(DeliveryMethod):
    method = METHOD_SMS
    MAX_MESSAGE_LENGTH = 158

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DEFAULT, {})
        kwargs[CONF_DEFAULT].setdefault(CONF_OPTIONS, {})
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_SIMPLIFY_TEXT, True)
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_STRIP_URLS, False)
        kwargs[CONF_DEFAULT][CONF_OPTIONS].setdefault(OPTION_MESSAGE_USAGE, MessageOnlyPolicy.COMBINE_TITLE)
        super().__init__(*args, **kwargs)

    def select_target(self, target: str) -> bool:
        return re.fullmatch(RE_VALID_PHONE, target) is not None

    def recipient_target(self, recipient: dict[str, Any]) -> list[str]:
        phone = recipient.get(CONF_PHONE_NUMBER)
        return [phone] if phone else []

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_sms: %s", envelope.delivery_name)

        data: dict[str, Any] = envelope.data or {}
        mobile_numbers = envelope.targets or []

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
