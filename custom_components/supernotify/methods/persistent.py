import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify import (
    ATTR_NOTIFICATION_ID,
    METHOD_PERSISTENT,
)
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery

_LOGGER = logging.getLogger(__name__)


class PersistentDeliveryMethod(DeliveryMethod):
    method = METHOD_PERSISTENT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_action(self) -> str:
        return "persistent_notification.create"

    def select_targets(self, target: Target) -> Target:  # noqa: ARG002
        return Target()

    @property
    def target_required(self) -> bool:
        return False

    async def deliver(self, envelope: Envelope) -> bool:
        data = envelope.data or {}
        config: Delivery = self.delivery_config(envelope.delivery_name)

        notification_id = data.get(ATTR_NOTIFICATION_ID) or config.data.get(ATTR_NOTIFICATION_ID)
        action_data = envelope.core_action_data()
        action_data["notification_id"] = notification_id

        return await self.call_action(envelope, action_data=action_data)
