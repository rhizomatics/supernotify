from homeassistant.const import CONF_ACTION, CONF_OPTIONS, CONF_TARGET

from custom_components.supernotify import CONF_DATA, CONF_DELIVERY, CONF_TRANSPORT, TRANSPORT_TTS
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.tts import TTSTransport

from .hass_setup_lib import TestingContext


async def test_transport_tts() -> None:
    ctx = TestingContext(
        deliveries={
            "all_speakers": {
                CONF_TRANSPORT: TRANSPORT_TTS,
                CONF_DATA: {"options": {"preferred_format": "wav"}},
                CONF_TARGET: ["media_player.kitchen_speakers"],
            }
        },
        services={"tts": ["speak"]},
    )
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "all_speakers", CONF_DATA: {"cache": False}})
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "tts",
        "speak",
        service_data={
            "message": "testing 123",
            "cache": False,
            "options": {"preferred_format": "wav"},
            "media_player_entity_id": "media_player.kitchen_speakers",
            "entity_id": "tts.home_assistant_cloud",
        },
        blocking=False,
        context=None,
        target={"entity_id": "tts.home_assistant_cloud"},
        return_response=False,
    )


def test_tts_transport_selects_targets() -> None:
    """Test on_notify_alexa."""
    context = TestingContext(deliveries={"announce": {CONF_TRANSPORT: TRANSPORT_TTS}})
    uut = Delivery("unit_testing", {}, TTSTransport(context, {}))

    assert uut.select_targets(Target(["switch.alexa_1", "media_player.hall_1"])).entity_ids == ["media_player.hall_1"]


async def test_override_to_legacy_action() -> None:
    ctx = TestingContext(
        deliveries={"all_speakers": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_ACTION: "tts.say"}}, services={"tts": ["speak"]}
    )
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123", target="media_player.kitchen_speakers")
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "tts",
        "say",
        service_data={
            "message": "testing 123",
            "media_player_entity_id": "media_player.kitchen_speakers",
            "entity_id": "tts.home_assistant_cloud",
        },
        blocking=False,
        context=None,
        target={"entity_id": "tts.home_assistant_cloud"},
        return_response=False,
    )


async def test_alt_tts_provider() -> None:
    ctx = TestingContext(
        deliveries={"all_speakers": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_OPTIONS: {"tts_entity_id": "tts.google_ai_tts"}}},
        services={"tts": ["speak"]},
    )
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123", target="media_player.kitchen_speakers")
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "tts",
        "speak",
        service_data={
            "message": "testing 123",
            "media_player_entity_id": "media_player.kitchen_speakers",
            "entity_id": "tts.google_ai_tts",
        },
        blocking=False,
        context=None,
        target={"entity_id": "tts.google_ai_tts"},
        return_response=False,
    )
