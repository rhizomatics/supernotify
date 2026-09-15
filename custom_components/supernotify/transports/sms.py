from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.const import (
    ATTR_PHONE,
    INCLUSION_DEFAULT,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_UNIQUE_TARGETS,
    TRANSPORT_SMS,
)
from custom_components.supernotify.model import (
    DebugTrace,
    EntityCategory,
    MessageOnlyPolicy,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class SMSTransport(Transport):
    name = TRANSPORT_SMS
    MAX_MESSAGE_LENGTH = 158

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def inclusion_mode(self) -> list[str]:
        # a phone number maps cleanly to a recipient, so it's reasonable to fire on
        # every notification by default
        return [INCLUSION_DEFAULT]

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.inclusion = self.inclusion_mode
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: False,
            OPTION_UNIQUE_TARGETS: True,  # disable if people get multiple deliveries on same number
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
    def target_categories(self) -> list[str | EntityCategory]:
        return [ATTR_PHONE]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        # like validate_action() below, an explicit delivery can supply its own action
        # regardless of whether a gateway service is discoverable here - is_viable() can't
        # see delivery-level config, so it can't rule that out; DeliveryRegistry prunes this
        # transport entirely once it's confirmed no delivery (explicit or auto) uses it
        return True

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        if self.delivery_defaults.action:
            return {self.name: {}}
        return {}

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is not None

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
