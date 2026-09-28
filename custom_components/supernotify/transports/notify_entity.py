from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.const import (
    RE_NOTIFY_ENTITY_ID,
    TRANSPORT_NOTIFY_ENTITY,
)
from custom_components.supernotify.model import (
    DebugTrace,
    MessageOnlyPolicy,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.options import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_SELECT,
)
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


FIXED_ACTION = "notify.send_message"


class NotifyEntityTransport(Transport):
    """Call any notify entity"""

    name = TRANSPORT_NOTIFY_ENTITY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def default_config(self) -> TransportConfig:
        config = super().default_config
        config.delivery_defaults.action = FIXED_ACTION
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_SELECT: [RE_NOTIFY_ENTITY_ID],
        }
        return config

    @property
    def fallback_target_categories(self) -> list[str | TargetEntityCategory]:
        # no platform restriction - the generic catch-all for any notify.* entity not
        # claimed by a more specific transport (html5, alexa_devices) - being `fallback`
        # rather than `unique` is what gives those first refusal, both for selection
        # (Notification.select_deliveries()) and ranking (default_selection_rank())
        return [TargetEntityCategory(domain="notify")]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return bool(hass_api.entity_ids_for_domain("notify"))

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        targets = envelope.target.entity_ids or []
        if not targets:
            _LOGGER.warning("SUPERNOTIFY notify_entity: no targets")
            return False
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}
        # area_id
        # device_id
        # label_id
        action_data = envelope.core_action_data()

        return await self.call_action(envelope, FIXED_ACTION, action_data=action_data, target_data=target_data)
