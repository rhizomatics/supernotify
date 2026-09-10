from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify.const import (
    ATTR_NOTIFICATION_ID,
    SELECTION_EXPLICIT,
    TRANSPORT_PERSISTENT,
)
from custom_components.supernotify.model import DebugTrace, DeliveryConfig, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class PersistentTransport(Transport):
    name = TRANSPORT_PERSISTENT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "persistent_notification.create"
        config.delivery_defaults.target_required = TargetRequired.NEVER
        return config

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        # persistent_notification is always available in HA core, no integration to discover -
        # but a UI popup on every single notification would be intrusive, so require opt-in
        delivery_config: DeliveryConfig = self.delivery_defaults
        delivery_config.selection = [SELECTION_EXPLICIT]
        return delivery_config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        data = envelope.data or {}

        notification_id = data.get(ATTR_NOTIFICATION_ID) or envelope.delivery.data.get(ATTR_NOTIFICATION_ID)
        action_data = envelope.core_action_data()
        if notification_id is not None:
            action_data["notification_id"] = notification_id

        return await self.call_action(envelope, action_data=action_data)
