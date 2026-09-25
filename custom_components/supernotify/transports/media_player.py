from __future__ import annotations

import logging
import urllib.parse
from typing import TYPE_CHECKING, Any, ClassVar

from homeassistant.const import (
    ATTR_ENTITY_ID,
)
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.const import (
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    RE_MEDIA_PLAYER_ENTITY_ID,
    TRANSPORT_MEDIA,
)
from custom_components.supernotify.model import DebugTrace, TransportConfig, TransportFeature
from custom_components.supernotify.options import MEDIA_OPTIONS, OPTION_TARGET_SELECT, DeliveryOption
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class MediaPlayerTransport(Transport):
    name = TRANSPORT_MEDIA
    declared_options: ClassVar[list[DeliveryOption]] = [*MEDIA_OPTIONS]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.IMAGES | TransportFeature.VIDEO | TransportFeature.SOUND | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "media_player.play_media"
        config.delivery_defaults.options = {
            OPTION_TARGET_SELECT: [RE_MEDIA_PLAYER_ENTITY_ID],
        }
        config.delivery_defaults.inclusion = self.inclusion_mode
        return config

    @property
    def target_categories(self) -> list[str | TargetEntityCategory]:
        return [TargetEntityCategory(domain="media_player")]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return bool(hass_api.entity_ids_for_domain("media_player"))

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

    async def _resolve_snapshot_url(self, envelope: Envelope, data: dict[str, Any]) -> str | None:
        """Resolve a snapshot URL for the media player to play.

        Order of resolution:
          1. An explicit snapshot_url in the media block (absolutised), unprocessed.
          2. envelope.grab_image() - respects delivery-specific `jpeg_opts`/`png_opts`/
             `reprocess` options - converted to a shareable URL via media_storage.object_url().
          3. None (caller skips the delivery).
        """
        snapshot_url = data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is None:
            # fallback to older idiosyncratic way for backward compatibility
            snapshot_url = data.get(ATTR_MEDIA_SNAPSHOT_URL)
        if snapshot_url is not None:
            # absolutize relative URL for external URl, probably preferred by Alexa Show etc
            return urllib.parse.urljoin(self.hass_api.external_url, snapshot_url)

        image_path = await envelope.grab_image()
        if image_path is None:
            return None
        return await self.context.media_storage.object_url(image_path)

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_media: %s", envelope.data)

        data: dict[str, Any] = envelope.data or {}
        media_players: list[str] = envelope.target.entity_ids or []
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY Skipping media show, no targets")
            return False

        content_id: str | None
        media_type: str
        explicit_content_id: str | None = data.get("media_content_id")
        if explicit_content_id:
            # Generic content (audio clip, video, stream, media-source:// id) - passed through
            # as-is, apart from relative URLs like /local/sounds/bell.mp3 which are absolutised
            # so remote players (Cast, Sonos etc) can fetch them. Defaults to `music` since
            # that is what most media players expect for an audio file.
            content_id = urllib.parse.urljoin(self.hass_api.external_url, explicit_content_id)
            media_type = data.get("media_content_type", "music")
        else:
            content_id = await self._resolve_snapshot_url(envelope, data)
            media_type = data.get("media_content_type", "image")
        if content_id is None:
            _LOGGER.debug("SUPERNOTIFY Skipping media player, no media_content_id or snapshot url")
            return False

        action_data: dict[str, Any] = {"media": {"media_content_id": content_id, "media_content_type": media_type}}
        if data and data.get("announce"):
            action_data["announce"] = data.get("announce")
        if data and data.get("enqueue"):
            action_data["enqueue"] = data.get("enqueue")

        return await self.call_action(envelope, action_data=action_data, target_data={ATTR_ENTITY_ID: media_players})
