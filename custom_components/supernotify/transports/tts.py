import logging
from typing import Any

from homeassistant.components.notify.const import ATTR_MESSAGE
from homeassistant.components.tts.const import ATTR_CACHE, ATTR_LANGUAGE, ATTR_OPTIONS
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    OPTION_TTS_ENTITY_ID,
    TRANSPORT_TTS,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import DebugTrace, MessageOnlyPolicy, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

_LOGGER = logging.getLogger(__name__)
RE_VALID_MEDIA_PLAYER = r"media_player\.[A-Za-z0-9_]+"
ATTR_MEDIA_PLAYER_ENTITY_ID = "media_player_entity_id"  # mypy flags up import from tts


class TTSTransport(Transport):
    """Notify via Home Assistant's built-in tts.speak action

    options:
        message_usage: standard | use_title | combine_title

    """

    name = TRANSPORT_TTS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE

    def validate_action(self, action: str | None) -> bool:
        """Allow default action to be overridden, such as tts.say or tts.cloud_speak"""
        return action is not None

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "tts.speak"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
            OPTION_TARGET_INCLUDE_RE: [RE_VALID_MEDIA_PLAYER],
            OPTION_TTS_ENTITY_ID: "tts.home_assistant_cloud",
        }
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY tts: %s", envelope.message)

        targets = envelope.target.entity_ids or []

        if not targets:
            _LOGGER.debug("SUPERNOTIFY skipping tts devices, no targets")
            return False

        action_data: dict[str, Any] = {ATTR_MESSAGE: envelope.message or ""}
        if ATTR_LANGUAGE in envelope.data:
            action_data[ATTR_LANGUAGE] = envelope.data[ATTR_LANGUAGE]
        if ATTR_CACHE in envelope.data:
            action_data[ATTR_CACHE] = envelope.data[ATTR_CACHE]
        if ATTR_OPTIONS in envelope.data:
            action_data[ATTR_OPTIONS] = envelope.data[ATTR_OPTIONS]
        target_data: dict[str, Any] = {ATTR_ENTITY_ID: envelope.delivery.options.get(OPTION_TTS_ENTITY_ID)}

        if targets and len(targets) == 1:
            action_data[ATTR_MEDIA_PLAYER_ENTITY_ID] = targets[0]
        else:
            # despite the docs, the tts code accepts a list of media_player entity ids
            action_data[ATTR_MEDIA_PLAYER_ENTITY_ID] = targets

        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
