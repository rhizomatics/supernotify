"""LG webOS TV transport for SuperNotify.

Shows a toast on LG webOS TVs set up with Home Assistant's `webostv` integration. That
integration has a legacy notify action for each TV, named after its config entry, such as
`notify.living_room_tv`, rather than a notify entity. So the TV's `media_player` entity is the
target, and each one is mapped to its notify action through its config entry. As an entity,
it can be reached by area, floor, label or device too.

Only the message is shown: the title is used only when there is no message.

TVs that are off, or unavailable, are skipped, since the integration can't reach them and
would otherwise raise an error.

Supported data keys (optional):
    icon    str     path to an image file on the Home Assistant host, shown as the toast's icon
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE
from homeassistant.const import ATTR_ICON, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from custom_components.supernotify.const import TRANSPORT_WEBOSTV
from custom_components.supernotify.model import DebugTrace, SuppressionReason, TransportFeature
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

HA_WEBOSTV_DOMAIN = "webostv"


class WebOsTvTransport(Transport):
    """Notify via a toast on LG webOS TVs, using the webostv integration"""

    name = TRANSPORT_WEBOSTV
    integration_domain = HA_WEBOSTV_DOMAIN

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE

    @property
    def unique_target_categories(self) -> list[str | TargetEntityCategory]:
        return [TargetEntityCategory(domain="media_player", platform=HA_WEBOSTV_DOMAIN)]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return hass_api.find_config_entry_data(HA_WEBOSTV_DOMAIN) is not None

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

    def validate_action(self, action: str | None) -> bool:
        """The action is found for each TV, not configured"""
        return action is None

    def notify_action(self, entity_id: str) -> str | None:
        """The TV's legacy notify action, named by the integration after its config entry"""
        title: str | None = self.hass_api.config_entry_title_for_entity(entity_id)
        if not title:
            return None
        service: str = slugify(title)
        return f"notify.{service}" if self.hass_api.has_service("notify", service) else None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY webostv %s", envelope.message)

        action_data: dict[str, Any] = {ATTR_MESSAGE: envelope.message or ""}
        icon: str | None = (envelope.data or {}).get(ATTR_ICON)
        if icon:
            action_data[ATTR_DATA] = {ATTR_ICON: icon}

        sent: int = 0
        for entity_id in envelope.target.entity_ids:
            state = self.hass_api.get_state(entity_id)
            if state is not None and state.state in (STATE_OFF, STATE_UNAVAILABLE):
                _LOGGER.debug("SUPERNOTIFY webostv skipping %s, which is %s", entity_id, state.state)
                continue
            action: str | None = self.notify_action(entity_id)
            if action is None:
                _LOGGER.warning("SUPERNOTIFY webostv no notify action found for %s", entity_id)
                continue
            if await self.call_action(
                envelope, qualified_action=action, action_data=dict(action_data), implied_target=True, single_target=True
            ):
                sent += 1

        if not sent and not envelope.error_count:
            envelope.skipped = 1
            envelope.skip_reason = SuppressionReason.NO_TARGET
        return sent > 0
