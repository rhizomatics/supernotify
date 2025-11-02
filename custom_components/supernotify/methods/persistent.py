import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify import (
    ATTR_NOTIFICATION_ID,
    CONF_DELIVERY_DEFAULTS,
    CONF_TARGETS_REQUIRED,
    METHOD_PERSISTENT,
    DeliveryConfig,
)
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery

_LOGGER = logging.getLogger(__name__)
ACTION = "persistent_notification.create"


class PersistentDeliveryMethod(DeliveryMethod):
    method = METHOD_PERSISTENT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DELIVERY_DEFAULTS, DeliveryConfig({}))
        kwargs[CONF_DELIVERY_DEFAULTS].action = ACTION
        kwargs[CONF_TARGETS_REQUIRED] = False
        super().__init__(*args, **kwargs)

    def validate_action(self, action: str | None) -> bool:
        return action is None or action == ACTION

    async def deliver(self, envelope: Envelope) -> bool:
        data = envelope.data or {}
        config: Delivery = self.delivery_config(envelope.delivery_name)

        notification_id = data.get(ATTR_NOTIFICATION_ID) or config.data.get(ATTR_NOTIFICATION_ID)
        action_data = envelope.core_action_data()
        action_data["notification_id"] = notification_id

        return await self.call_action(envelope, action_data=action_data)
