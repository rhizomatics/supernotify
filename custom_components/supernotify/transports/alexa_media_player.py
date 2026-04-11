"""Alexa Media Player transport adaptor for Supernotify.

Volume management: Amazon Alexa API does not expose a per-announcement
volume parameter in notify.alexa_media. This adaptor handles it natively:

1. Snapshot  - reads current volume_level of every target media_player.
               If None (AMP startup bug, issue #1394), uses volume_fallback.
2. Pause/Stop- If pause_music=True and playing: media_pause only (preserves
               streaming session for resume). No media_stop — calling it after
               media_pause kills Spotify/streaming and prevents resume.
             - If pause_music=False and playing: media_stop only (suppresses
               Alexa beep before volume_set; no resume expected).
             - If idle: neither (media_stop on idle Alexa triggers a beep).
3. Set vol   - media_player.volume_set on every target.
4. Announce  - notify.alexa_media without volume in payload.
5. Wait      - estimates TTS duration, SSML-aware (energywave/multinotify).
               Skipped when wait_for_tts=False (default) and no volume/music
               restore is needed (fire-and-forget mode).
               Duration calibrated per-language via tts_char_speed.
6. Resume    - media_player.media_play after 2s delay if was playing.
7. Restore   - media_player.volume_set back to previous level.
               No media_stop in post-announce: Alexa is already idle after
               TTS, calling media_stop would produce another unwanted beep.

Data keys (all optional):
    volume          float 0-1   desired announcement volume
    restore_volume  bool        restore previous volume (default True)
    pause_music     bool        pause music if playing (default True)
    volume_fallback float 0-1   fallback when volume_level is None (default 0.5)
    wait_for_tts    bool        block until TTS finishes before returning.
                                Default False (fire-and-forget).
                                Set True to sequence automation actions after
                                the announcement (e.g. "open blinds only after
                                Alexa has finished speaking").
                                When volume/music restore is active this wait
                                happens implicitly; wait_for_tts=True only adds
                                extra blocking in pure fire-and-forget deliveries.
    tts_char_speed  float s/ch  seconds per character for TTS duration estimate.
                                Default 0.06 (Italian/English calibration).
                                Suggested values by language family:
                                  Italian / English / French  : 0.060
                                  Spanish / Portuguese        : 0.058
                                  German                      : 0.065
                                  Russian / Polish            : 0.062
                                  Japanese / Chinese / Korean : 0.180
                                  Arabic                      : 0.075

References:
- energywave/multinotify https://github.com/energywave/multinotify
- ago19800/centralino    https://github.com/ago19800/centralino
- jumping2000/universal_notifier https://github.com/jumping2000/universal_notifier
- AMP issue #1394 https://github.com/alandtse/alexa_media_player/issues/1394
- AMP discussion #2782 https://github.com/alandtse/alexa_media_player/discussions/2782
- multinotify issue #6  https://github.com/energywave/multinotify/issues/6

"""

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_SELECT,
    OPTION_UNIQUE_TARGETS,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
)
from custom_components.supernotify.model import (
    DebugTrace,
    MessageOnlyPolicy,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

RE_VALID_ALEXA = r"media_player\.[A-Za-z0-9_]+"


RE_SSML_TAG = re.compile(r"<[^>]+>")
PAUSE_CHARS = (", ", ". ", "! ", "? ", ": ", "; ")

# ref: https://github.com/alandtse/alexa_media_player/wiki/Configuration%3A-Notification-Component
SERVICE_DATA_KEYS = [ATTR_MESSAGE, ATTR_TITLE, ATTR_DATA, ATTR_TARGET]
SERVICE_DATA_DATA_KEYS = ["type", "method"]

_PAUSE_WEIGHT = 0.35
_CHAR_WEIGHT = 0.06
_BASE_DURATION = 5.0
_MUSIC_RESUME_DELAY = 2.0

_LOGGER = logging.getLogger(__name__)


def _estimate_tts_duration(message: str, char_weight: float = _CHAR_WEIGHT) -> float:
    """Estimate pronunciation duration in seconds, stripping SSML first.

    Formula from energywave/multinotify:
        duration = BASE + pause_chars x PAUSE_WEIGHT + chars x char_weight

    Args:
        message:     The TTS message (SSML tags are stripped before counting).
        char_weight: Seconds per plain-text character.  Override via the
                     ``tts_char_speed`` data key to calibrate for the TTS
                     language (default 0.06 s/ch — Italian/English).

    """
    plain = RE_SSML_TAG.sub("", message)
    pause_count = sum(plain.count(p) for p in PAUSE_CHARS)
    return _BASE_DURATION + pause_count * _PAUSE_WEIGHT + len(plain) * char_weight


class AlexaMediaPlayerTransport(Transport):
    """Notify via Amazon Alexa announcements with full volume management.

    options:
        message_usage: standard | use_title | combine_title
    """

    name = TRANSPORT_ALEXA_MEDIA_PLAYER

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.SPOKEN

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "notify.alexa_media"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: True,
            OPTION_STRIP_URLS: True,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_UNIQUE_TARGETS: True,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
            OPTION_TARGET_SELECT: [RE_VALID_ALEXA],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        return action is not None

    async def _safe_service(self, domain: str, service: str, service_data: dict[str, Any]) -> bool:
        """Call a HA service via hass_api, catching exceptions so offline devices never block overall delivery."""
        try:
            await self.hass_api.call_service(domain, service, service_data=service_data)
            return True
        except Exception as exc:
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: %s.%s failed for %s: %s",
                domain,
                service,
                service_data.get(ATTR_ENTITY_ID, "unknown"),
                exc,
            )
            return False

    async def _snapshot_states(self, media_players: list[str], volume_fallback: float) -> dict[str, dict[str, Any]]:
        """Read volume and playback state for every target.

        Uses volume_fallback when volume_level is None (AMP issue #1394).
        """
        states: dict[str, dict[str, Any]] = {}
        for mp in media_players:
            state = self.hass_api.get_state(mp)
            if state is None:
                _LOGGER.debug("SUPERNOTIFY alexa_media_player: %s not found", mp)
                continue
            vol = state.attributes.get("volume_level")
            if vol is None:
                _LOGGER.debug(
                    "SUPERNOTIFY alexa_media_player: %s volume_level None, using fallback %.2f (AMP issue #1394)",
                    mp,
                    volume_fallback,
                )
                vol = volume_fallback
            states[mp] = {"volume": float(vol), "playing": state.state == "playing"}
        return states

    async def _pre_announce(
        self,
        states: dict[str, dict[str, Any]],
        requested_volume: float,
        pause_music: bool,
    ) -> set[str]:
        """Pause music, stop beep, set announcement volume."""
        volume_set_failed: set[str] = set()
        for mp, prev in states.items():
            if prev["playing"]:
                if pause_music:
                    # Pause only — do NOT also call media_stop.
                    # media_stop after media_pause kills streaming sessions
                    # (Spotify, etc.) making them impossible to resume later.
                    # media_pause leaves the session alive for media_play resume.
                    await self._safe_service("media_player", "media_pause", {ATTR_ENTITY_ID: mp})
                else:
                    # Not pausing: use media_stop to suppress the Alexa
                    # confirmation beep before volume_set (no resume expected).
                    await self._safe_service("media_player", "media_stop", {ATTR_ENTITY_ID: mp})
            if not await self._safe_service(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: mp, "volume_level": requested_volume},
            ):
                volume_set_failed.add(mp)
        return volume_set_failed

    async def _post_announce(
        self,
        states: dict[str, dict[str, Any]],
        restore_volume: bool,
        pause_music: bool,
    ) -> None:
        """Restore volume and resume music after announcement."""
        music_devices = [mp for mp, s in states.items() if pause_music and s["playing"]]
        for mp, prev in states.items():
            # Do NOT call media_stop here: after TTS finishes Alexa is already
            # idle, so media_stop would produce an unwanted confirmation beep.
            if restore_volume:
                await self._safe_service(
                    "media_player",
                    "volume_set",
                    {ATTR_ENTITY_ID: mp, "volume_level": prev["volume"]},
                )
        if music_devices:
            await asyncio.sleep(_MUSIC_RESUME_DELAY)
            for mp in music_devices:
                await self._safe_service("media_player", "media_play", {ATTR_ENTITY_ID: mp})

    async def deliver(
        self,
        envelope: Envelope,
        debug_trace: DebugTrace | None = None,  # noqa: ARG002
    ) -> bool:
        _LOGGER.debug("SUPERNOTIFY notify_alexa_media %s", envelope.message)

        media_players = envelope.target.entity_ids or []
        if not media_players:
            _LOGGER.debug("SUPERNOTIFY skipping alexa media player, no targets")
            return False

        # envelope.data is a flat dict — keys like volume, type, method
        # are at the top level, not nested under a "data" key.
        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        volume_raw = raw_data.pop("volume", None)
        restore_volume: bool = boolify(raw_data.pop("restore_volume", True), default=True)
        pause_music: bool = boolify(raw_data.pop("pause_music", True), default=True)
        volume_fallback: float = float(raw_data.pop("volume_fallback", 0.5))
        wait_for_tts: bool = boolify(raw_data.pop("wait_for_tts", False), default=False)
        tts_char_speed: float = float(raw_data.pop("tts_char_speed", _CHAR_WEIGHT))

        # Resolve Jinja2 template if volume is still a raw template string
        # (scenarios store volume as a template; _resolve_data_templates only
        # runs for archiving, not for delivery).
        requested_volume: float | None = None
        if isinstance(volume_raw, str) and "{{" in volume_raw:
            try:
                context_vars = (
                    cast("dict[str, Any]", envelope.condition_variables.as_dict()) if envelope.condition_variables else {}
                )
                rendered = self.hass_api.template(volume_raw).async_render(variables=context_vars)
                requested_volume = float(rendered)
                _LOGGER.debug("SUPERNOTIFY alexa_media_player: resolved volume template to %.2f", requested_volume)
            except Exception as exc:
                _LOGGER.warning("SUPERNOTIFY alexa_media_player: failed to resolve volume template %r: %s", volume_raw, exc)
        elif volume_raw is not None:
            try:
                requested_volume = float(volume_raw)
            except TypeError, ValueError:
                _LOGGER.warning("SUPERNOTIFY alexa_media_player: invalid volume value %r, ignoring", volume_raw)

        # Pre-announce
        states: dict[str, dict[str, Any]] = {}
        needs_restore = requested_volume is not None or pause_music

        if needs_restore:
            states = await self._snapshot_states(media_players, volume_fallback)

        volume_set_failed: set[str] = set()
        if requested_volume is not None and states:
            volume_set_failed = await self._pre_announce(states, requested_volume, pause_music)
        elif pause_music and states:
            for mp, prev in states.items():
                if prev["playing"]:
                    await self._safe_service("media_player", "media_pause", {ATTR_ENTITY_ID: mp})

        # Announce
        call_type: str = raw_data.get(ATTR_DATA, {}).get("type", "announce")
        action_data: dict[str, Any] = {
            "message": envelope.message,
            ATTR_DATA: {"type": call_type},
            ATTR_TARGET: media_players,
        }
        if requested_volume is not None and volume_set_failed:
            # Fallback path: if pre-announce volume_set fails for one or more
            # players, pass volume through notify.alexa_media too.
            action_data[ATTR_DATA]["volume"] = requested_volume

        result = await self.call_action(envelope, action_data=action_data)

        # Post-announce: optionally wait for TTS, then restore volume / resume music.
        # needs_post_announce is True whenever there is something to undo (volume change
        # or music was paused); in that case the TTS wait is always performed so the
        # restore/resume happens after Alexa finishes speaking.
        # wait_for_tts additionally blocks even in pure fire-and-forget deliveries,
        # allowing automation sequences to run only after the announcement ends.
        needs_post_announce = needs_restore and bool(states)
        if (needs_post_announce or wait_for_tts) and envelope.message:
            tts_duration = _estimate_tts_duration(envelope.message, tts_char_speed)
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: waiting %.1f s for TTS (%d chars, %.3f s/ch)",
                tts_duration,
                len(RE_SSML_TAG.sub("", envelope.message)),
                tts_char_speed,
            )
            await asyncio.sleep(tts_duration)
            if needs_post_announce:
                await self._post_announce(states, restore_volume and requested_volume is not None, pause_music)

        return result
