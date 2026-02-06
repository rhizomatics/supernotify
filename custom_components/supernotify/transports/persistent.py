import logging
from typing import Any

from custom_components.supernotify.const import (
    ATTR_NOTIFICATION_ID,
    TRANSPORT_PERSISTENT,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

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

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        data = envelope.data or {}

        notification_id = data.get(ATTR_NOTIFICATION_ID) or envelope.delivery.data.get(ATTR_NOTIFICATION_ID)
        action_data = envelope.core_action_data()
        action_data["notification_id"] = notification_id

        return await self.call_action(envelope, action_data=action_data)
