from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.const import ATTR_TOPIC, TRANSPORT_MQTT
from custom_components.supernotify.model import (
    DebugTrace,
    SuppressionReason,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

HA_MQTT_DOMAIN = "mqtt"
# what mqtt.publish accepts besides `topic` - its schema rejects any other key, and a notification's
# own `data`, meant for other deliveries, reaches every delivery
PUBLISH_DATA_KEYS = ("payload", "qos", "retain", "evaluate_payload", "message_expiry_interval")

_LOGGER = logging.getLogger(__name__)


class MQTTTransport(Transport):
    name = TRANSPORT_MQTT
    integration_domain = HA_MQTT_DOMAIN

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE

    @property
    def default_config(self) -> TransportConfig:
        config = super().default_config
        config.delivery_defaults.action = "mqtt.publish"
        # a topic can come from a `data:` keyword instead of a target (see deliver()
        # below), so this can't be inferred ALWAYS like most transports with a
        # unique_target_categories entry - Notification._target_required() covers the gap
        # this leaves for an implicit-only, category-less-at-a-glance selection
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.delivery_defaults.options = {}
        return config

    @property
    def unique_target_categories(self) -> list[str | TargetEntityCategory]:
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

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

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
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_TARGET
            return False

        dropped: list[str] = sorted(k for k in data if k not in PUBLISH_DATA_KEYS)
        if dropped:
            _LOGGER.debug("SUPERNOTIFY notify_mqtt: dropping data keys mqtt.publish doesn't accept: %s", dropped)
        data = {k: v for k, v in data.items() if k in PUBLISH_DATA_KEYS}

        payload: Any = data.get("payload")
        if isinstance(payload, (dict, list)):
            data["payload"] = json.dumps(payload)
        elif payload is None:
            data["payload"] = envelope.message

        success = True
        for topic in topics:
            action_data: dict[str, Any] = dict(data)
            action_data[ATTR_TOPIC] = topic
            success = await self.call_action(envelope, action_data=action_data) and success
        return success
