import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues

from custom_components.supernotify import CONF_DELIVERY_DEFAULTS, CONF_TARGETS_REQUIRED, METHOD_NOTIFY_ENTITY, DeliveryConfig
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)


class NotifyEntityDeliveryMethod(DeliveryMethod):
    """Call any notify entity"""

    method = METHOD_NOTIFY_ENTITY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DELIVERY_DEFAULTS, DeliveryConfig({}))
        kwargs[CONF_TARGETS_REQUIRED] = True
        super().__init__(*args, **kwargs)

    @property
    def default_action(self) -> str:
        return "notify.send_message"

    async def deliver(self, envelope: Envelope) -> bool:
        action_data = envelope.core_action_data()
        targets = envelope.targets or []
        if not targets:
            raise ValueError("No targets for notify entity method")
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}
        # area_id
        # device_id
        # label_id
        action_data = envelope.core_action_data()

        return await self.call_action(envelope, self.default_action, action_data=action_data, target_data=target_data)
