import logging
from typing import Any

from homeassistant.const import CONF_ACTION, CONF_DEFAULT

from custom_components.supernotify import ATTR_NOTIFICATION_ID, CONF_TARGETS_REQUIRED, METHOD_PERSISTENT
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)
ACTION = "persistent_notification.create"


class PersistentDeliveryMethod(DeliveryMethod):
    method = METHOD_PERSISTENT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DEFAULT, {})
        kwargs[CONF_DEFAULT].setdefault(CONF_ACTION, ACTION)
        kwargs.setdefault(CONF_TARGETS_REQUIRED, False)
        super().__init__(*args, **kwargs)

    def validate_action(self, action: str | None) -> bool:
        return action is None or action == ACTION

    async def deliver(self, envelope: Envelope) -> bool:
        data = envelope.data or {}
        config = self.delivery_config(envelope.delivery_name)

        notification_id = data.get(ATTR_NOTIFICATION_ID, config.get(ATTR_NOTIFICATION_ID))
        action_data = envelope.core_action_data()
        action_data["notification_id"] = notification_id

        return await self.call_action(envelope, action_data=action_data)
