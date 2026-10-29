from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET

from custom_components.supernotify.const import (
    ATTR_PHONE,
    TRANSPORT_SMS,
)
from custom_components.supernotify.model import (
    DebugTrace,
    MessageOnlyPolicy,
    SuppressionReason,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.options import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
)
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class SMSTransport(Transport):
    name = TRANSPORT_SMS
    action_configured = True
    MAX_MESSAGE_LENGTH = 158

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def default_config(self) -> TransportConfig:
        config = super().default_config
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.COMBINE_TITLE,
        }
        for module in (
            "homeassistant.components.twilio_sms.notify",
            "custom_components.mikrotik_sms.notify",
        ):
            action: str | None = self.hass_api.find_service("notify", module)
            if action:
                config.delivery_defaults.action = action
                _LOGGER.info("SUPERNOTIFY SMS action defaults to %s", action)
                break
        return config

    @property
    def unique_target_categories(self) -> list[str | TargetEntityCategory]:
        return [ATTR_PHONE]

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is not None

    def simplify(self, text: str | None, strip_urls: bool = False) -> str | None:
        """Remove emoji and other pictographic symbols, but not currency signs, brackets or maths
        symbols as for a voice assistant, since SMS can carry these and the message needs them"""
        if not text:
            return None
        if strip_urls:
            text = self._strip_urls(text)
        text = unicodedata.normalize("NFC", text)
        return "".join(c for c in text if unicodedata.category(c) not in ("So", "Sk", "Mn"))

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_sms: %s", envelope.delivery_name)

        data: dict[str, Any] = envelope.data or {}
        # resolved_targets(), not the typed `.phone` getter: envelope.target is already
        # scoped to this delivery by Delivery.select_targets(), so this also picks up a
        # `sms:`/`{sms: ...}`-qualified number that isn't shaped like a validated one
        # (e.g. a short code)
        mobile_numbers = envelope.target.resolved_targets() if envelope.target else []

        if not envelope.message:
            _LOGGER.warning("SUPERNOTIFY notify_sms: No message to send")
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.INVALID_ACTION_DATA
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
