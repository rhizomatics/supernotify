from unittest.mock import Mock, call

from homeassistant.const import ATTR_ENTITY_ID, CONF_DEFAULT, CONF_METHOD

from custom_components.supernotify import CONF_DATA, METHOD_CHIME
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.chime import ChimeDeliveryMethod
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass, mock_context) -> None:  # type: ignore
    """Test on_notify_chime"""
    uut = ChimeDeliveryMethod(
        mock_hass,
        mock_context,
        {"chimes": {CONF_METHOD: METHOD_CHIME, CONF_DEFAULT: True}},
    )
    mock_context.deliveries = {"chimes": Delivery("chime", {}, uut)}

    device = Mock(identifiers={("alexa_devices", "ffffee8484848484")})
    device_registry = Mock()
    device_registry.async_get.return_value = device
    mock_context.device_registry = Mock(return_value=device_registry)

    # await context.initialize()

    await uut.initialize()

    envelope = Envelope(
        "chimes",
        Notification(mock_context, message="for script only"),
        targets=[
            "switch.bell_1",
            "script.alarm_2",
            "media_player.living_room",
            "siren.lobby",
            "ffff0000eeee1111dddd2222cccc3333",
        ],
        data={"chime_tune": "boing_01", "chime_duration": 10, "chime_volume": 1},
    )
    await uut.deliver(envelope)
    assert envelope.skipped == 0
    assert envelope.delivered == 1

    mock_hass.services.async_call.assert_has_calls(
        [
            call("switch", "turn_on", service_data={}, target={"entity_id": "switch.bell_1"}),
            call(
                "alexa_devices",
                "send_sound",
                service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "boing_01"},
            ),
            call(
                "siren",
                "turn_on",
                target={"entity_id": "siren.lobby"},
                service_data={"data": {"duration": 10, "volume_level": 1, "tone": "boing_01"}},
            ),
            call(
                "script",
                "alarm_2",
                service_data={
                    "variables": {
                        "message": "for script only",
                        "title": None,
                        "priority": "medium",
                        "chime_tune": "boing_01",
                        "chime_volume": 1,
                        "chime_duration": 10,
                    }
                },
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.living_room"},
                service_data={
                    "media_content_id": "boing_01",
                    "media_content_type": "sound",
                },
            ),
        ],
        any_order=True,
    )
    assert len(envelope.calls) == 5


async def test_deliver_alias(mock_hass) -> None:  # type: ignore
    """Test on_notify_chime"""
    delivery_config = {"chimes": {CONF_METHOD: METHOD_CHIME, CONF_DEFAULT: True, CONF_DATA: {"chime_tune": "doorbell"}}}
    context = Context()
    uut = ChimeDeliveryMethod(
        mock_hass,
        context,
        delivery_config,
        delivery_defaults={
            "target": ["media_player.kitchen_alexa", "media_player.hall_echo", "ffff0000eeee1111dddd2222cccc3333"],
            "options": {
                "chime_aliases": {
                    "doorbell": {
                        "media_player_hall": {
                            "tune": "home/amzn_sfx_doorbell_chime_01",
                            "target": "media_player.hall_echo",
                        },
                        "media_player": "home/amzn_sfx_doorbell_chime_02",
                        "alexa_devices": "bell01",
                        "switch": {"target": "switch.chime_ding_dong"},
                        "script": {
                            "target": "script.front_door_bell",
                            "data": {"variables": {"visitor_name": "Guest"}},
                        },
                    }
                }
            },
        },
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()

    envelope = Envelope("chimes", Notification(context, message="for script only"))
    await uut.deliver(envelope)
    assert envelope.skipped == 0
    assert envelope.errored == 0
    assert envelope.delivered == 1

    mock_hass.services.async_call.assert_has_calls(
        [
            call("switch", "turn_on", service_data={}, target={"entity_id": "switch.chime_ding_dong"}),
            call(
                "alexa_devices", "send_sound", service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "bell01"}
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.kitchen_alexa"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "home/amzn_sfx_doorbell_chime_02",
                },
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.hall_echo"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "home/amzn_sfx_doorbell_chime_01",
                },
            ),
            call(
                "script",
                "front_door_bell",
                service_data={
                    "variables": {
                        "message": "for script only",
                        "title": None,
                        "priority": "medium",
                        "chime_tune": "doorbell",
                        "visitor_name": "Guest",
                        "chime_volume": None,
                        "chime_duration": None,
                    }
                },
            ),
        ],
        any_order=True,
    )
    assert len(envelope.calls) == 5


class MockGroup:
    def __init__(self, entities: list[str]) -> None:
        self.attributes = {ATTR_ENTITY_ID: entities}


async def test_deliver_to_group(mock_hass) -> None:  # type: ignore
    """Test on_notify_chime"""
    groups = {
        "group.alexa": MockGroup(["media_player.alexa_1", "media_player.alexa_2"]),
        "group.chime": MockGroup(["switch.bell_1"]),
    }
    delivery_config = {
        "chimes": {
            CONF_METHOD: METHOD_CHIME,
            CONF_DEFAULT: True,
            CONF_DATA: {"chime_tune": "dive_dive_dive"},
        }
    }
    context = Context()
    await context.initialize()
    mock_hass.states.get.side_effect = lambda v: groups.get(v)
    uut = ChimeDeliveryMethod(mock_hass, context, delivery_config)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()

    await uut.deliver(Envelope("chimes", Notification(context), targets=["group.alexa", "group.chime", "script.siren_2"]))
    mock_hass.services.async_call.assert_has_calls(
        [
            call(
                "script",
                "siren_2",
                service_data={
                    "variables": {
                        "message": None,
                        "title": None,
                        "priority": "medium",
                        "chime_tune": "dive_dive_dive",
                        "chime_volume": None,
                        "chime_duration": None,
                    }
                },
            ),
            call("switch", "turn_on", service_data={}, target={"entity_id": "switch.bell_1"}),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.alexa_1"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "dive_dive_dive",
                },
            ),
        ],
        any_order=True,
    )
