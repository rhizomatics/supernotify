import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET

from custom_components.supernotify import CONF_DELIVERY_DEFAULTS, METHOD_ALEXA_MEDIA_PLAYER, DeliveryConfig, MessageOnlyPolicy
from custom_components.supernotify.delivery import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
)
from custom_components.supernotify.delivery_method import (
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope

RE_VALID_ALEXA = r"media_player\.[A-Za-z0-9_]+"
ACTION = "notify.alexa_media"

_LOGGER = logging.getLogger(__name__)


class AlexaMediaPlayerDeliveryMethod(DeliveryMethod):
    """Notify via Amazon Alexa announcements

    options:
        message_usage: standard | use_title | combine_title

    """

    method = METHOD_ALEXA_MEDIA_PLAYER

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_DELIVERY_DEFAULTS, DeliveryConfig({}))
        if not kwargs[CONF_DELIVERY_DEFAULTS].action:
            kwargs[CONF_DELIVERY_DEFAULTS].action = ACTION
        kwargs[CONF_DELIVERY_DEFAULTS].options.setdefault(OPTION_SIMPLIFY_TEXT, True)
        kwargs[CONF_DELIVERY_DEFAULTS].options.setdefault(OPTION_STRIP_URLS, True)
        kwargs[CONF_DELIVERY_DEFAULTS].options.setdefault(OPTION_MESSAGE_USAGE, MessageOnlyPolicy.STANDARD)
        super().__init__(*args, **kwargs)

    def select_target(self, target: str) -> bool:
        return re.fullmatch(RE_VALID_ALEXA, target) is not None

    async def deliver(self, envelope: Envelope) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_media %s", envelope.message)

        media_players = envelope.targets or []

        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping alexa media player, no targets")
            return False

        action_data: dict[str, Any] = {"message": envelope.message, ATTR_DATA: {"type": "announce"}, ATTR_TARGET: media_players}
        # alexa media player expects a non-std list as target, so don't use notify target arg (which expects dict)
        if envelope.data and envelope.data.get("data"):
            action_data[ATTR_DATA].update(envelope.data.get("data"))
        return await self.call_action(envelope, action_data=action_data)
