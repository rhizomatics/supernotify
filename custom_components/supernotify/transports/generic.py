import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues

from custom_components.supernotify import CONF_DATA, TRANSPORT_GENERIC
from custom_components.supernotify.common import ensure_list
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy
from custom_components.supernotify.transport import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery

_LOGGER = logging.getLogger(__name__)


class GenericTransport(Transport):
    """Call any service, including non-notify ones, like switch.turn_on or mqtt.publish"""

    transport = TRANSPORT_GENERIC

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def target_required(self) -> bool:
        # target might be implicit in the service depending on how generic configured
        return False

    @property
    def default_options(self) -> dict[str, Any]:
        return {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
        }

    def validate_action(self, action: str | None) -> bool:
        if action is not None and "." in action:
            return True
        _LOGGER.warning("SUPERNOTIFY generic transport must have a qualified action name, e.g. notify.foo")
        return False

    async def deliver(self, envelope: Envelope) -> bool:
        data = envelope.data or {}
        config: Delivery = self.delivery_config(envelope.delivery_name)

        qualified_action = config.action
        if qualified_action and qualified_action.startswith("notify."):
            action_data = envelope.core_action_data()
            if data and qualified_action != "notify.send_message":
                action_data[CONF_DATA] = data
        else:
            action_data = data

        target_data: dict[str, Any] = {}
        if config.action == "notify.send_message":
            # amongst the wild west of notifty handling, at least care for the modern core one
            target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
        else:
            all_targets: list[str] = []
            for category in ensure_list(config.option(OPTION_TARGET_CATEGORIES)):
                all_targets.extend(envelope.target.for_category(category))
            if all_targets:
                action_data[ATTR_TARGET] = all_targets

        return await self.call_action(envelope, qualified_action, action_data=action_data, target_data=target_data)
