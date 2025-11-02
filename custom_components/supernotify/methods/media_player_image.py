import logging
import re
import urllib.parse
from typing import Any

from custom_components.supernotify import CONF_DELIVERY_DEFAULTS, CONF_TARGETS_REQUIRED, METHOD_MEDIA, DeliveryConfig
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

RE_VALID_MEDIA_PLAYER = r"media_player\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)


class MediaPlayerImageDeliveryMethod(DeliveryMethod):
    """Requires Alex Media Player integration"""

    method = METHOD_MEDIA

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DELIVERY_DEFAULTS, DeliveryConfig({}))
        kwargs[CONF_TARGETS_REQUIRED] = False
        super().__init__(*args, **kwargs)

    @property
    def default_action(self) -> str:
        return "media_player.play_media"

    def select_target(self, target: str) -> bool:
        return re.fullmatch(RE_VALID_MEDIA_PLAYER, target) is not None

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_media: %s", envelope.data)

        data: dict[str, Any] = envelope.data or {}
        media_players: list[str] = envelope.targets or []
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping media show, no targets")
            return False

        snapshot_url = data.get("snapshot_url")
        if snapshot_url is None:
            _LOGGER.debug("SUPERNOTIFY skipping media player, no image url")
            return False
        # absolutize relative URL for external URl, probably preferred by Alexa Show etc
        snapshot_url = urllib.parse.urljoin(self.context.hass_external_url, snapshot_url)

        action_data: dict[str, Any] = {
            "media_content_id": snapshot_url,
            "media_content_type": "image",
            "entity_id": media_players,
        }
        if data and data.get("data"):
            action_data["extra"] = data.get("data", {})

        return await self.call_action(envelope, action_data=action_data)
