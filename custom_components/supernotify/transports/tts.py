import logging
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE
from homeassistant.components.tts.const import ATTR_CACHE, ATTR_LANGUAGE, ATTR_OPTIONS
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify import (
    ATTR_MOBILE_APP_ID,
    CONF_MANUFACTURER,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    OPTION_TTS_ENTITY_ID,
    TRANSPORT_TTS,
    SelectionRank,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import (
    DebugTrace,
    MessageOnlyPolicy,
    Target,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

_LOGGER = logging.getLogger(__name__)
RE_VALID_MEDIA_PLAYER = r"media_player\.[A-Za-z0-9_]+"
RE_MOBILE_APP = r"(notify\.)?mobile_app_[a-z0-9_]+"
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
        config.delivery_defaults.selection_rank = SelectionRank.FIRST
        config.device_discovery = False
        config.device_domain = ["mobile_app"]
        config.device_manufacturer_exclude = ["Apple"]
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID, ATTR_MOBILE_APP_ID],
            OPTION_TARGET_INCLUDE_RE: [RE_VALID_MEDIA_PLAYER, RE_MOBILE_APP],
            OPTION_TTS_ENTITY_ID: "tts.home_assistant_cloud",
        }
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY tts: %s", envelope.message)

        delivered: bool = False

        media_player_targets = envelope.target.entity_ids or []
        if media_player_targets:
            delivered = await self.call_media_players(envelope, media_player_targets)

        mobile_targets = envelope.target.mobile_app_ids or []
        if mobile_targets:
            if await self.call_mobile_apps(envelope, mobile_targets):
                delivered = True
        return delivered

    async def call_media_players(self, envelope: Envelope, targets: list[str]) -> bool:
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

    async def call_mobile_apps(self, envelope: Envelope, targets: list[str]) -> bool:
        action_data: dict[str, Any] = {ATTR_MESSAGE: "TTS", ATTR_DATA: {"tts_text": envelope.message or ""}}
        if "media_stream" in envelope.data:
            action_data["media_stream"] = envelope.data["media_stream"]

        at_least_one: bool = False
        for target in targets:
            bare_target = target.replace("notify.", "", 1) if target.startswith("notify.") else target
            mobile_info = self.context.hass_api.mobile_app_by_id(bare_target)
            if not mobile_info or mobile_info.get(CONF_MANUFACTURER) == "Apple":
                _LOGGER.debug("SUPERNOTIFY Skipping tts target that isn't confirmed as android: %s", mobile_info)
            else:
                full_target = target if Target.is_notify_entity(target) else f"notify.{target}"
                if await self.call_action(envelope, qualified_action=full_target, action_data=action_data, implied_target=True):
                    at_least_one = True
        return at_least_one
