from typing import TYPE_CHECKING

from homeassistant.const import CONF_ACTION, CONF_OPTIONS, CONF_TARGET

from custom_components.supernotify.const import ATTR_SPOKEN_MESSAGE, CONF_DATA, CONF_DELIVERY, CONF_TRANSPORT, TRANSPORT_TTS
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.tts import TTSTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, assert_clean_notification, register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.common import CallRecord


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


async def test_transport_spoken_msg_override() -> None:
    ctx = TestingContext(
        deliveries={
            "all_speakers": {
                CONF_TRANSPORT: TRANSPORT_TTS,
                CONF_TARGET: ["media_player.kitchen_speakers"],
            }
        },
        services={"tts": ["speak"]},
    )
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "all_speakers", ATTR_SPOKEN_MESSAGE: "yoo hoo"})
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "tts",
        "speak",
        service_data={
            "message": "yoo hoo",
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


async def test_manual_android_tts_provider(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries={"phone_tts": {CONF_TRANSPORT: TRANSPORT_TTS}})
    register_mobile_app(ctx.hass_api, device_name="jeans_phone", manufacturer="Apple")
    register_mobile_app(ctx.hass_api, device_name="bobs_phone", manufacturer="Xiaomi")
    await ctx.test_initialize()
    n = Notification(
        ctx, "testing 123", target=["mobile_app_bobs_phone", "mobile_app_jeans_phone"], action_data={"delivery": "phone_tts"}
    )
    await n.initialize()
    await n.deliver()

    assert_clean_notification(n, expected_deliveries={"phone_tts": 1})
    assert len(n.deliveries["phone_tts"]["delivered"][0].calls) == 1  # type: ignore
    # type: ignore
    call: CallRecord = n.deliveries["phone_tts"]["delivered"][0].calls[0]  # type: ignore
    assert call.domain == "notify"
    assert call.action == "mobile_app_bobs_phone"
    assert call.action_data == {"message": "TTS", "data": {"tts_text": "testing 123"}}


async def test_multiple_media_player_targets() -> None:
    ctx = TestingContext(
        deliveries={"all_speakers": {CONF_TRANSPORT: TRANSPORT_TTS}},
        services={"tts": ["speak"]},
    )
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123", target=["media_player.kitchen_speakers", "media_player.living_room"])
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "tts",
        "speak",
        service_data={
            "message": "testing 123",
            "media_player_entity_id": ["media_player.kitchen_speakers", "media_player.living_room"],
            "entity_id": "tts.home_assistant_cloud",
        },
        blocking=False,
        context=None,
        target={"entity_id": "tts.home_assistant_cloud"},
        return_response=False,
    )


async def test_tts_with_language_option() -> None:
    ctx = TestingContext(
        deliveries={"all_speakers": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_DATA: {"language": "fr-FR"}}},
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
            "language": "fr-FR",
            "media_player_entity_id": "media_player.kitchen_speakers",
            "entity_id": "tts.home_assistant_cloud",
        },
        blocking=False,
        context=None,
        target={"entity_id": "tts.home_assistant_cloud"},
        return_response=False,
    )


async def test_mobile_tts_with_media_stream(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries={"phone_tts": {CONF_TRANSPORT: TRANSPORT_TTS}})
    register_mobile_app(ctx.hass_api, device_name="bobs_phone", manufacturer="Xiaomi")
    await ctx.test_initialize()
    n = Notification(
        ctx,
        "testing 123",
        target=["mobile_app_bobs_phone"],
        action_data={"delivery": "phone_tts", "data": {"media_stream": "alarm_stream"}},
    )
    await n.initialize()
    await n.deliver()

    assert_clean_notification(n, expected_deliveries={"phone_tts": 1})
    call: CallRecord = n.deliveries["phone_tts"]["delivered"][0].calls[0]  # type: ignore
    assert call.action_data == {"message": "TTS", "data": {"tts_text": "testing 123"}, "media_stream": "alarm_stream"}


async def test_auto_android_tts_provider(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"phone_tts": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_OPTIONS: {"device_discovery": True}}},
        transport_types=[TTSTransport],
    )
    register_mobile_app(ctx.hass_api, device_name="jeans_phone", manufacturer="Apple")
    register_mobile_app(ctx.hass_api, device_name="bobs_phone", manufacturer="Xiaomi")
    await ctx.test_initialize()
    n = Notification(ctx, "testing 123")
    await n.initialize()
    await n.deliver()

    assert_clean_notification(n, expected_deliveries={"phone_tts": 1})
    assert len(n.deliveries["phone_tts"]["delivered"][0].calls) == 1  # type: ignore
    # type: ignore
    call: CallRecord = n.deliveries["phone_tts"]["delivered"][0].calls[0]  # type: ignore
    assert call.domain == "notify"
    assert call.action == "mobile_app_bobs_phone"
    assert call.action_data == {"message": "TTS", "data": {"tts_text": "testing 123"}}
