import json
import logging
from typing import Any

from homeassistant.components.mqtt.const import ATTR_TOPIC

from custom_components.supernotify import METHOD_MQTT
from custom_components.supernotify.delivery_method import (
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target

RE_VALID_PHONE = r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$"

_LOGGER = logging.getLogger(__name__)


class MQTTDeliveryMethod(DeliveryMethod):
    method = METHOD_MQTT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_options(self) -> dict[str, Any]:
        return {}

    @property
    def default_action(self) -> str:
        return "mqtt.publish"

    @property
    def target_required(self) -> bool:
        return False

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if delivery method has fixed action or doesn't require one"""
        return action == self.default_action

    def select_targets(self, target: Target) -> Target:  # noqa: ARG002
        return Target()

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
