import logging
import re
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues

from custom_components.supernotify import TRANSPORT_NOTIFY_ENTITY
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.transport import Transport

_LOGGER = logging.getLogger(__name__)

RE_NOTIFY_ENTITY = r"notify\.[A-Za-z0-9_]+"


class NotifyEntityTransport(Transport):
    """Call any notify entity"""

    name = TRANSPORT_NOTIFY_ENTITY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def select_targets(self, target: Target) -> Target:
        # TODO: handle group expansion
        return Target({"entity_id": [e for e in target.entity_ids if re.fullmatch(RE_NOTIFY_ENTITY, e) is not None]})

    @property
    def default_action(self) -> str:
        return "notify.send_message"

    @property
    def auto_configure(self) -> bool:
        return True

    async def deliver(self, envelope: Envelope) -> bool:
        action_data = envelope.core_action_data()
        targets = envelope.target.entity_ids or []
        if not targets:
            raise ValueError("No targets for notify entity transport")
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}
        # area_id
        # device_id
        # label_id
        action_data = envelope.core_action_data()

        return await self.call_action(envelope, self.default_action, action_data=action_data, target_data=target_data)
