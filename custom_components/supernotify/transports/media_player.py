from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
)

from custom_components.supernotify.const import (
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_SELECT,
    RE_MEDIA_PLAYER_ENTITY_ID,
    TRANSPORT_MEDIA,
)
from custom_components.supernotify.model import DebugTrace, DeliveryConfig, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class MediaPlayerTransport(Transport):
    name = TRANSPORT_MEDIA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.IMAGES | TransportFeature.VIDEO | TransportFeature.SOUND

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "media_player.play_media"
        config.delivery_defaults.options = {
            OPTION_TARGET_SELECT: [RE_MEDIA_PLAYER_ENTITY_ID],
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
        }
        config.delivery_defaults.inclusion = self.inclusion_mode
        return config

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:
        if not hass_api.entity_ids_for_domain("media_player"):
            return None
        return self.delivery_defaults

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_media: %s", envelope.data)

        data: dict[str, Any] = envelope.data or {}
        media_players: list[str] = envelope.target.entity_ids or []
        media_type: str = data.get("media_content_type", "image")
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY Skipping media show, no targets")
            return False

        snapshot_url = data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is None:
            # fallback to older idiosyncratic way for backward compatibility
            snapshot_url = data.get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is None:
            _LOGGER.debug("SUPERNOTIFY Skipping media player, no snapshot url")
            return False
        # absolutize relative URL for external URl, probably preferred by Alexa Show etc
        snapshot_url = urllib.parse.urljoin(self.hass_api.external_url, snapshot_url)

        action_data: dict[str, Any] = {"media": {"media_content_id": snapshot_url, "media_content_type": media_type}}
        if data and data.get("announce"):
            action_data["announce"] = data.get("announce")
        if data and data.get("enqueue"):
            action_data["enqueue"] = data.get("enqueue")

        return await self.call_action(envelope, action_data=action_data, target_data={ATTR_ENTITY_ID: media_players})
