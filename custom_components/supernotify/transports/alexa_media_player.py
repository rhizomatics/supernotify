"""Alexa Media Player transport adaptor for Supernotify.

Sends announcements to Amazon Echo devices via the alexa_media_player
custom integration (https://github.com/alandtse/alexa_media_player).

Volume management
-----------------
Amazon's Alexa API does not expose a per-announcement volume parameter in
notify.alexa_media, so setting ``volume`` inside the ``data:`` block of a
delivery or scenario has *no effect* on the actual playback level.

This adaptor therefore handles volume natively:

1. Snapshot - reads the current ``volume_level`` attribute of every target
   media_player before the announcement. If the attribute is ``None``
   (a known Alexa Media Player quirk at HA startup, see AMP issue #1394
   https://github.com/alandtse/alexa_media_player/issues/1394), the
   ``volume_fallback`` option is used instead (default 0.5).

2. Stop beep - issues ``media_player.media_stop`` before changing volume.
   Without this Alexa emits an audible confirmation beep on every volume
   change. Workaround from energywave/multinotify
   (https://github.com/energywave/multinotify).

3. Set volume - calls ``media_player.volume_set`` on every target.

4. Announce - calls ``notify.alexa_media`` as before, but with ``volume``
   removed from the data payload (Alexa ignores it anyway).

5. Wait - estimates announcement duration from message length and natural
   pause characters, stripping SSML tags first so the timing is accurate
   even when whispering effects or prosody tags are used.
   Formula (from energywave/multinotify):
       duration = 5 + pause_chars x 0.35 + plain_text_chars x 0.06

6. Music resume - if a device was playing before the announcement, waits
   an extra 2 s for the volume change to settle, then calls
   ``media_player.media_play`` to resume. The 2-second delay prevents
   music from resuming at the announcement volume (ago19800/centralino).

7. Restore volume - restores every device to its original level.

All pre/post service calls use blocking=False and are individually wrapped
in try/except so that a single offline device never blocks or fails the
entire delivery.

New data: keys recognised by this transport (all optional):
    volume          float 0.0-1.0  - desired announcement volume
    restore_volume  bool           - restore previous volume (default True)
    pause_music     bool           - pause music if playing (default True)
    volume_fallback float 0.0-1.0  - fallback when volume_level is None
                                     (default 0.5)

Inspiration & references
------------------------
- Multinotify (Henrik Sozzi / energywave)
  https://github.com/energywave/multinotify
  pause/resume music, media_stop beep workaround, TTS duration formula,
  SSML-aware text-length calculation, volume snapshot/restore pattern.

- Centralino Manager (ago19800)
  https://github.com/ago19800/centralino
  time-slot volumes, music snapshot & restore, volume_fallback concept.

- Universal Notifier (jumping2000 / caiosweet)
  https://github.com/jumping2000/universal_notifier
  asyncio concurrency model, full media-player state snapshot.

- Alexa Media Player issue #1394 (alandtse)
  https://github.com/alandtse/alexa_media_player/issues/1394
  volume_level attribute missing at HA startup.

- Alexa Media Player discussion #2782 (alandtse)
  https://github.com/alandtse/alexa_media_player/discussions/2782
  community attempts to add volume to notify.alexa_media.
"""

import asyncio
import logging
import re
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.const import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_SELECT,
    OPTION_UNIQUE_TARGETS,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import (
    DebugTrace,
    MessageOnlyPolicy,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

RE_VALID_ALEXA = r"media_player\.[A-Za-z0-9_]+"
RE_SSML_TAG = re.compile(r"<[^>]+>")
PAUSE_CHARS = (", ", ". ", "! ", "? ", ": ", "; ")

_PAUSE_WEIGHT = 0.35
_CHAR_WEIGHT = 0.06
_BASE_DURATION = 5.0
_MUSIC_RESUME_DELAY = 2.0

_LOGGER = logging.getLogger(__name__)


def _estimate_tts_duration(message: str) -> float:
    """Estimate how many seconds Alexa needs to pronounce message.

    SSML tags are stripped first so markup does not inflate the count.
    Formula from energywave/multinotify:
        duration = BASE + pause_chars x PAUSE_WEIGHT + chars x CHAR_WEIGHT
    """
    plain = RE_SSML_TAG.sub("", message)
    pause_count = sum(plain.count(p) for p in PAUSE_CHARS)
    return _BASE_DURATION + pause_count * _PAUSE_WEIGHT + len(plain) * _CHAR_WEIGHT


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
        return TransportFeature.MESSAGE

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
        """Override in subclass if transport has fixed action."""
        return action is not None

    async def _safe_service(
        self, domain: str, service: str, service_data: dict[str, Any]
    ) -> None:
        """Call a HA service, swallowing exceptions so one offline device
        never blocks or fails the overall delivery."""
        try:
            await self.hass.services.async_call(
                domain, service, service_data, blocking=False
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: %s.%s failed for %s",
                domain,
                service,
                service_data.get(ATTR_ENTITY_ID, "unknown"),
            )

    async def _snapshot_states(
        self, media_players: list[str], volume_fallback: float
    ) -> dict[str, dict[str, Any]]:
        """Read current volume and playback state for every target device.

        If volume_level is None (AMP startup bug, issue #1394) the
        volume_fallback value is stored so restore always works.
        """
        states: dict[str, dict[str, Any]] = {}
        for mp in media_players:
            state = self.hass.states.get(mp)
            if state is None:
                _LOGGER.debug("SUPERNOTIFY alexa_media_player: %s not found", mp)
                continue
            vol = state.attributes.get("volume_level")
            if vol is None:
                _LOGGER.debug(
                    "SUPERNOTIFY alexa_media_player: %s volume_level is None, "
                    "using fallback %.2f (AMP issue #1394)",
                    mp,
                    volume_fallback,
                )
                vol = volume_fallback
            states[mp] = {
                "volume": float(vol),
                "playing": state.state == "playing",
            }
        return states

    async def _pre_announce(
        self,
        states: dict[str, dict[str, Any]],
        requested_volume: float,
        pause_music: bool,
    ) -> None:
        """Pause music (if playing) and set announcement volume.

        media_player.media_stop before volume_set suppresses the audible
        beep Alexa emits on every volume change (energywave/multinotify
        workaround).
        """
        for mp, prev in states.items():
            if pause_music and prev["playing"]:
                _LOGGER.debug(
                    "SUPERNOTIFY alexa_media_player: pausing music on %s", mp
                )
                await self._safe_service(
                    "media_player", "media_pause", {ATTR_ENTITY_ID: mp}
                )
            await self._safe_service(
                "media_player", "media_stop", {ATTR_ENTITY_ID: mp}
            )
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: setting volume %.2f on %s",
                requested_volume,
                mp,
            )
            await self._safe_service(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: mp, "volume_level": requested_volume},
            )

    async def _post_announce(
        self,
        states: dict[str, dict[str, Any]],
        restore_volume: bool,
        pause_music: bool,
    ) -> None:
        """Restore volume and resume music after announcement.

        2-second delay before media_play ensures volume_set has been
        applied before music restarts (ago19800/centralino pattern).
        """
        music_devices = [
            mp for mp, s in states.items() if pause_music and s["playing"]
        ]
        for mp, prev in states.items():
            await self._safe_service(
                "media_player", "media_stop", {ATTR_ENTITY_ID: mp}
            )
            if restore_volume:
                _LOGGER.debug(
                    "SUPERNOTIFY alexa_media_player: restoring volume %.2f on %s",
                    prev["volume"],
                    mp,
                )
                await self._safe_service(
                    "media_player",
                    "volume_set",
                    {ATTR_ENTITY_ID: mp, "volume_level": prev["volume"]},
                )
        if music_devices:
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: waiting %ss before resuming music",
                _MUSIC_RESUME_DELAY,
            )
            await asyncio.sleep(_MUSIC_RESUME_DELAY)
            for mp in music_devices:
                _LOGGER.debug(
                    "SUPERNOTIFY alexa_media_player: resuming music on %s", mp
                )
                await self._safe_service(
                    "media_player", "media_play", {ATTR_ENTITY_ID: mp}
                )

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

        # Extract volume-management keys and pop them so they are NOT
        # forwarded to notify.alexa_media (Alexa ignores them anyway).
        raw_data: dict[str, Any] = {}
        if envelope.data and envelope.data.get("data"):
            raw_data = dict(envelope.data["data"])

        requested_volume: float | None = raw_data.pop("volume", None)
        restore_volume: bool = bool(raw_data.pop("restore_volume", True))
        pause_music: bool = bool(raw_data.pop("pause_music", True))
        volume_fallback: float = float(raw_data.pop("volume_fallback", 0.5))

        # Pre-announce: snapshot -> stop beep -> pause music -> set volume
        states: dict[str, dict[str, Any]] = {}
        needs_restore = requested_volume is not None or pause_music

        if needs_restore:
            states = await self._snapshot_states(media_players, volume_fallback)

        if requested_volume is not None and states:
            await self._pre_announce(states, requested_volume, pause_music)
        elif pause_music and states:
            for mp, prev in states.items():
                if prev["playing"]:
                    await self._safe_service(
                        "media_player", "media_pause", {ATTR_ENTITY_ID: mp}
                    )

        # Announce
        action_data: dict[str, Any] = {
            "message": envelope.message,
            ATTR_DATA: {"type": "announce"},
            ATTR_TARGET: media_players,
        }
        if raw_data:
            action_data[ATTR_DATA].update(raw_data)

        result = await self.call_action(envelope, action_data=action_data)

        # Post-announce: wait -> restore volume -> resume music
        if needs_restore and states:
            duration = _estimate_tts_duration(envelope.message)
            _LOGGER.debug(
                "SUPERNOTIFY alexa_media_player: waiting %.1fs for TTS to finish",
                duration,
            )
            await asyncio.sleep(duration)
            await self._post_announce(states, restore_volume, pause_music)

        return result
