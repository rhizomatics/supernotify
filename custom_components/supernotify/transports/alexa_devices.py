from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.group.const import DOMAIN as HA_GROUP_DOMAIN
from homeassistant.components.notify.const import ATTR_MESSAGE
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.const import (
    INCLUSION_DEFAULT,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_SELECT,
    OPTION_UNIQUE_TARGETS,
    RE_NOTIFY_ENTITY_ID,
    TRANSPORT_ALEXA,
)
from custom_components.supernotify.model import (
    DebugTrace,
    DeliveryConfig,
    EntityCategory,
    MessageOnlyPolicy,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.schema import SelectionRank
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

HA_ALEXA_DEVICES_DOMAIN = "alexa_devices"
# the entity registry platform for notify entities the integration itself creates -
# singular, unlike the (plural) config entry/integration domain above
HA_ALEXA_DEVICES_PLATFORM = "alexa_device"
# alandtse/alexa_media_player HACS integration's notify platform module - kept in sync
# with the constant of the same name in alexa_media_player.py
HA_ALEXA_MEDIA_PLAYER_MODULE = "custom_components.alexa_media.notify"


class AlexaDevicesTransport(Transport):
    """Notify via Home Assistant's built-in Alexa Devices integration

    options:
        message_usage: standard | use_title | combine_title

    """

    name = TRANSPORT_ALEXA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.SPOKEN

    @property
    def inclusion_mode(self) -> list[str]:
        # Notify Entity based
        return [INCLUSION_DEFAULT]

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "notify.send_message"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.selection_rank = SelectionRank.FIRST
        config.delivery_defaults.inclusion = self.inclusion_mode
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_UNIQUE_TARGETS: True,
            # an HA group (not owned by any platform) or one of this integration's own
            # notify entities (identified by platform, not just its entity_id shape)
            OPTION_TARGET_SELECT: [r"group\.[a-z0-9_]+", RE_NOTIFY_ENTITY_ID],
        }
        return config

    @property
    def target_categories(self) -> list[str | EntityCategory]:
        return [
            EntityCategory(domain="notify", platform=HA_ALEXA_DEVICES_PLATFORM),
            # an HA group isn't owned by any platform - membership/expansion isn't handled
            # here yet (only chime.py does that), so it's accepted at face value
            EntityCategory(domain=HA_GROUP_DOMAIN),
        ]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        if hass_api.find_config_entry_data(HA_ALEXA_DEVICES_DOMAIN) is None:
            return False
        # integration installed but no Alexa device has registered a notify entity yet
        return bool(hass_api.entity_ids_for_platform("notify", HA_ALEXA_DEVICES_PLATFORM))

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        return self.delivery_defaults

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_devices: %s", envelope.message)

        targets = envelope.target.entity_ids or []

        if not targets:
            _LOGGER.debug("SUPERNOTIFY Skipping alexa devices, no targets")
            return False

        action_data: dict[str, Any] = {ATTR_MESSAGE: envelope.message or ""}
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: targets}

        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
