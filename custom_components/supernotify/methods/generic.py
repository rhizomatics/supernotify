import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import (  # ATTR_VARIABLES from script.const has import issues
    ATTR_ENTITY_ID,
)

from custom_components.supernotify import CONF_DATA, CONF_TARGETS_REQUIRED, METHOD_GENERIC
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery

_LOGGER = logging.getLogger(__name__)


class GenericDeliveryMethod(DeliveryMethod):
    """Call any service, including non-notify ones, like switch.turn_on or mqtt.publish"""

    method = METHOD_GENERIC

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_TARGETS_REQUIRED, False)
        super().__init__(*args, **kwargs)

    def validate_action(self, action: str | None) -> bool:
        if action is not None and "." in action:
            return True
        _LOGGER.warning("SUPERNOTIFY generic method must have a qualified action name, e.g. notify.foo")
        return False

    async def deliver(self, envelope: Envelope) -> bool:
        data = envelope.data or {}
        targets = envelope.targets or []
        config: Delivery = self.delivery_config(envelope.delivery_name)
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets} if targets else {}

        qualified_action = config.action
        if qualified_action and qualified_action.startswith("notify."):
            action_data = envelope.core_action_data()
            if data is not None:
                action_data[CONF_DATA] = data
        else:
            action_data = data

        return await self.call_action(envelope, qualified_action, action_data=action_data, target_data=target_data)
