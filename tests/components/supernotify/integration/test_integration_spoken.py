"""End to end flows through the tts, media and alexa_media_player transports, on a real Home Assistant"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er

from .framework import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONFIG = """
delivery:
  speak:
    transport: tts
  speak_legacy:
    transport: tts
    action: tts.cloud_say
  show:
    transport: media
  echo:
    transport: alexa_media_player
    action: notify.alexa_media
"""

STUB_ACTIONS = [
    "tts.speak",
    "tts.cloud_say",
    "media_player.play_media",
    "media_player.volume_set",
    "media_player.media_pause",
    "media_player.media_play",
    "notify.alexa_media",
]


async def spoken_house(hass: HomeAssistant) -> House:
    # no Nabu Casa `tts.home_assistant_cloud`, so the tts transport has to find its own entity
    hass.states.async_set("tts.piper", "unknown")
    hass.states.async_set("media_player.kitchen", "idle")
    echo = er.async_get(hass).async_get_or_create("media_player", "alexa_media", "echo_id", suggested_object_id="echo")
    hass.states.async_set(echo.entity_id, "playing", {"volume_level": 0.3})
    # registered ahead of setup, so the transports are viable - House replaces them with recording stubs
    for action in STUB_ACTIONS:
        domain, service = action.split(".", 1)
        hass.services.async_register(domain, service, AsyncMock())
    house = House(
        users={"Bob": "bob"},
        android_apps={"bob_phone": "Bob"},
        cameras={"porch": None},
        config=CONFIG,
        stub_actions=STUB_ACTIONS,
    )
    await house.setup(hass)
    return house


def calls(house: House, domain: str, service: str) -> list[ServiceCall]:
    return [c for c in house.service_calls.get(domain, []) if c.service == service]


async def test_tts_speaks_on_media_player_and_android_app(hass: HomeAssistant) -> None:
    house = await spoken_house(hass)
    try:
        await house.call("""
            message: Dinner is ready
            delivery: speak
            target:
              - media_player.kitchen
              - mobile_app_bob_phone
            data:
              media_stream: alarm_stream
        """)
        (speak,) = calls(house, "tts", "speak")
        assert speak.data == {
            "message": "Dinner is ready",
            "media_player_entity_id": "media_player.kitchen",
            "entity_id": "tts.piper",
        }
        (android,) = calls(house, "notify", "mobile_app_bob_phone")
        assert android.data == {"message": "TTS", "data": {"tts_text": "Dinner is ready", "media_stream": "alarm_stream"}}
    finally:
        house.cleanup()


async def test_tts_legacy_say_action_targets_media_players(hass: HomeAssistant) -> None:
    house = await spoken_house(hass)
    try:
        await house.call("""
            message: Dinner is ready
            delivery: speak_legacy
            target: media_player.kitchen
        """)
        (say,) = calls(house, "tts", "cloud_say")
        assert say.data == {"message": "Dinner is ready", "entity_id": ["media_player.kitchen"]}
    finally:
        house.cleanup()


async def test_media_shows_camera_image(hass: HomeAssistant) -> None:
    house = await spoken_house(hass)
    try:
        await house.call("""
            message: ""
            delivery: show
            target: media_player.kitchen
            media:
              camera_entity_id: camera.porch
        """)
        (play,) = calls(house, "media_player", "play_media")
        assert play.data["entity_id"] == ["media_player.kitchen"]
        assert play.data["media"]["media_content_type"] == "image"
        image_url: str = play.data["media"]["media_content_id"]
        assert image_url.startswith("http")
        entry = hass.config_entries.async_entries("supernotify")[0]
        image_path = image_url.split(entry.runtime_data.context.media_storage.media_url_prefix, 1)[1]
        assert house._camera_for_image(await house.image_bytes(image_path)) == "camera.porch"
    finally:
        house.cleanup()


async def test_alexa_media_player_volume_from_template_set_and_restored(hass: HomeAssistant) -> None:
    house = await spoken_house(hass)
    try:
        # no waiting for the speech to finish or music to resume, without changing the clock for all of HA
        with (
            patch("custom_components.supernotify.transports.alexa_media_player._estimate_tts_duration", return_value=0),
            patch("custom_components.supernotify.transports.alexa_media_player._MUSIC_RESUME_DELAY", 0),
        ):
            await house.call("""
                message: Dinner is ready
                delivery:
                  echo:
                    data:
                      volume: "{{ 60 / 100 }}"
                target: media_player.echo
            """)
        sequence = [(c.domain, c.service, c.data.get("volume_level")) for c in house.service_calls.get("media_player", [])]
        assert sequence == [
            ("media_player", "media_pause", None),
            ("media_player", "volume_set", 0.6),
            ("media_player", "volume_set", 0.3),
            ("media_player", "media_play", None),
        ]
        (announce,) = calls(house, "notify", "alexa_media")
        assert announce.data == {
            "message": "Dinner is ready",
            "data": {"type": "announce"},
            "target": ["media_player.echo"],
        }
    finally:
        house.cleanup()
