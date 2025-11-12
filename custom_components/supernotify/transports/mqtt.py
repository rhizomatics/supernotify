import json
import logging
from typing import Any

from homeassistant.components.mqtt.const import ATTR_TOPIC

from custom_components.supernotify import TRANSPORT_MQTT
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target, TransportConfig
from custom_components.supernotify.transport import (
    Transport,
)

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class MQTTTransport(Transport):
    name = TRANSPORT_MQTT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "mqtt.publish"
        config.delivery_defaults.target_required = False
        config.delivery_defaults.options = {}
        return config

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is self.delivery_defaults.action

    def recipient_target(self, recipient: dict[str, Any]) -> Target | None:  # noqa: ARG002
        return None

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_mqtt: %s", envelope.delivery_name)

        if not envelope.data or ATTR_TOPIC not in envelope.data:
            _LOGGER.warning("SUPERNOTIFY notify_mqtt: No topic for publication")
        action_data: dict[str, Any] = envelope.data
        if isinstance(action_data["payload"], dict):
            action_data["payload"] = json.dumps(action_data["payload"])
        return await self.call_action(envelope, action_data=action_data)
