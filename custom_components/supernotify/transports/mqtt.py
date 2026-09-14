from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify.const import ATTR_TOPIC, TRANSPORT_MQTT
from custom_components.supernotify.model import (
    DebugTrace,
    DeliveryConfig,
    EntityCategory,
    Target,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

HA_MQTT_DOMAIN = "mqtt"

_LOGGER = logging.getLogger(__name__)


class MQTTTransport(Transport):
    name = TRANSPORT_MQTT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "mqtt.publish"
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.delivery_defaults.options = {}
        config.delivery_defaults.inclusion = self.inclusion_mode
        return config

    @property
    def target_categories(self) -> list[str | EntityCategory]:
        # `topic` is a clean, dedicated category name for the mapping form (`target: {topic:
        # ...}`), distinct from overloading the transport's own name (`target: {mqtt: ...}`,
        # still handled separately by Delivery.select_targets()). A bare, unqualified
        # `target: <topic>` set directly on the mqtt delivery block also reaches here - not
        # via this list, but because it's the sole plain-string entry `Delivery.
        # reclassify_unqualified_target()` falls back to for a delivery-scoped value with no
        # shape a validator recognises.
        return [ATTR_TOPIC]

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action == self.delivery_defaults.action

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return hass_api.find_config_entry_data(HA_MQTT_DOMAIN) is not None

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        return self.delivery_defaults

    def recipient_target(self, recipient: dict[str, Any]) -> Target | None:
        return None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_mqtt: %s", envelope.delivery_name)

        data: dict[str, Any] = dict(envelope.data) if envelope.data else {}
        # envelope.target is already scoped to this transport by delivery.select_targets()
        # (see target_categories above), so any resolved target here is a topic
        topics: list[str] = envelope.target.resolved_targets() if envelope.target else []
        if topics:
            data.pop(ATTR_TOPIC, None)
        else:
            topic = data.pop(ATTR_TOPIC, None)
            if topic:
                topics = [topic]

        if not topics:
            _LOGGER.warning("SUPERNOTIFY notify_mqtt: No topic for publication")
            return False

        if isinstance(data.get("payload"), dict):
            data["payload"] = json.dumps(data["payload"])
        else:
            data["payload"] = envelope.message

        success = True
        for topic in topics:
            action_data: dict[str, Any] = dict(data)
            action_data[ATTR_TOPIC] = topic
            success = await self.call_action(envelope, action_data=action_data) and success
        return success
