import logging
import re
import urllib.parse
from typing import Any

from custom_components.supernotify import TRANSPORT_MEDIA
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.transport import Transport

RE_VALID_MEDIA_PLAYER = r"media_player\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)


class MediaPlayerImageTransport(Transport):
    """Requires Alex Media Player integration"""

    transport = TRANSPORT_MEDIA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_options(self) -> dict[str, Any]:
        return {}

    @property
    def default_action(self) -> str:
        return "media_player.play_media"

    def select_targets(self, target: Target) -> Target:
        return Target({"entity_id": [e for e in target.entity_ids if re.fullmatch(RE_VALID_MEDIA_PLAYER, e) is not None]})

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_media: %s", envelope.data)

        data: dict[str, Any] = envelope.data or {}
        media_players: list[str] = envelope.target.entity_ids or []
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping media show, no targets")
            return False

        snapshot_url = data.get("snapshot_url")
        if snapshot_url is None:
            _LOGGER.debug("SUPERNOTIFY skipping media player, no image url")
            return False
        # absolutize relative URL for external URl, probably preferred by Alexa Show etc
        snapshot_url = urllib.parse.urljoin(self.hass_api.external_url, snapshot_url)

        action_data: dict[str, Any] = {
            "media_content_id": snapshot_url,
            "media_content_type": "image",
            "entity_id": media_players,
        }
        if data and data.get("data"):
            action_data["extra"] = data.get("data", {})

        return await self.call_action(envelope, action_data=action_data)
