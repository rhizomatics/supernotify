import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET

from custom_components.supernotify import TRANSPORT_ALEXA_MEDIA_PLAYER
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, Target
from custom_components.supernotify.transport import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    Transport,
)

RE_VALID_ALEXA = r"media_player\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)


class AlexaMediaPlayerTransport(Transport):
    """Notify via Amazon Alexa announcements

    options:
        message_usage: standard | use_title | combine_title

    """

    transport = TRANSPORT_ALEXA_MEDIA_PLAYER

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_action(self) -> str:
        return "notify.alexa_media"

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action is not None

    @property
    def default_options(self) -> dict[str, Any]:
        return {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
        }

    def select_targets(self, target: Target) -> Target:
        return Target({"entity_id": [e for e in target.entity_ids if re.fullmatch(RE_VALID_ALEXA, e) is not None]})

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_media %s", envelope.message)

        media_players = envelope.target.entity_ids or []

        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping alexa media player, no targets")
            return False

        action_data: dict[str, Any] = {"message": envelope.message, ATTR_DATA: {"type": "announce"}, ATTR_TARGET: media_players}
        # alexa media player expects a non-std list as target, so don't use notify target arg (which expects dict)
        if envelope.data and envelope.data.get("data"):
            action_data[ATTR_DATA].update(envelope.data.get("data"))
        return await self.call_action(envelope, action_data=action_data)
