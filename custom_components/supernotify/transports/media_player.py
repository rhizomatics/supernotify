import logging
import urllib.parse
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
)

from custom_components.supernotify import OPTION_TARGET_CATEGORIES, OPTION_TARGET_INCLUDE_RE, TRANSPORT_MEDIA
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import TransportConfig
from custom_components.supernotify.transport import Transport

RE_VALID_MEDIA_PLAYER = r"media_player\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)


class MediaPlayerTransport(Transport):
    name = TRANSPORT_MEDIA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "media_player.play_media"
        config.delivery_defaults.options = {
            OPTION_TARGET_INCLUDE_RE: [RE_VALID_MEDIA_PLAYER],
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
        }
        return config

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_media: %s", envelope.data)

        data: dict[str, Any] = envelope.data or {}
        media_players: list[str] = envelope.target.entity_ids or []
        media_type: str = data.get("media_content_type", "image")
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping media show, no targets")
            return False

        snapshot_url = data.get("snapshot_url")
        if snapshot_url is None:
            _LOGGER.debug("SUPERNOTIFY skipping media player, no snapshot url")
            return False
        # absolutize relative URL for external URl, probably preferred by Alexa Show etc
        snapshot_url = urllib.parse.urljoin(
            self.hass_api.external_url, snapshot_url)

        action_data: dict[str, Any] = {
            "media": {"media_content_id": snapshot_url, "media_content_type": media_type}}
        if data and data.get("announce"):
            action_data["announce"] = data.get("announce")
        if data and data.get("enqueue"):
            action_data["enqueue"] = data.get("enqueue")

        return await self.call_action(envelope, action_data=action_data, target_data={ATTR_ENTITY_ID: media_players})
