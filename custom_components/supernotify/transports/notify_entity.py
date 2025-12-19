import logging
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues
from homeassistant.exceptions import ServiceValidationError

from custom_components.supernotify import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    OPTION_UNIQUE_TARGETS,
    TRANSPORT_NOTIFY_ENTITY,
    SelectionRank,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, TransportConfig
from custom_components.supernotify.transport import (
    Transport,
)

_LOGGER = logging.getLogger(__name__)

RE_NOTIFY_ENTITY = r"notify\.[A-Za-z0-9_]+"
FIXED_ACTION = "notify.send_message"


class NotifyEntityTransport(Transport):
    """Call any notify entity"""

    name = TRANSPORT_NOTIFY_ENTITY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = FIXED_ACTION
        config.delivery_defaults.selection_rank = SelectionRank.LAST
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_UNIQUE_TARGETS: True,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
            OPTION_TARGET_INCLUDE_RE: [RE_NOTIFY_ENTITY],
        }
        return config

    @property
    def auto_configure(self) -> bool:
        return True

    async def deliver(self, envelope: Envelope) -> bool:
        action_data = envelope.core_action_data()
        targets = envelope.target.entity_ids or []
        if not targets:
            raise ServiceValidationError("No targets for notify entity transport")
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}
        # area_id
        # device_id
        # label_id
        action_data = envelope.core_action_data()

        return await self.call_action(envelope, FIXED_ACTION, action_data=action_data, target_data=target_data)
