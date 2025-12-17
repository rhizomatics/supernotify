from unittest.mock import call

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify import CONF_DATA, CONF_DEVICE_DISCOVERY, CONF_TRANSPORT, TRANSPORT_CHIME
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.chime import ChimeTransport

from .hass_setup_lib import TestingContext


async def test_deliver() -> None:
    """Test on_notify_chime"""
    context = TestingContext(
        deliveries={"chimes": {CONF_TRANSPORT: TRANSPORT_CHIME}},
        devices=[("alexa_devices", "ffff0000eeee1111dddd2222cccc3333", False)],
    )

    uut = ChimeTransport(context, {CONF_DEVICE_DISCOVERY: True})
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    envelope = Envelope(
        Delivery("chimes", context.delivery_config("chimes"), uut),
        Notification(context, message="for script only"),
        target=Target([
            "switch.bell_1",
            "script.alarm_2",
            "media_player.living_room",
            "siren.lobby",
            "ffff0000eeee1111dddd2222cccc3333",
        ]),
        data={"chime_tune": "boing_01", "chime_duration": 10, "chime_volume": 1},
    )
    await uut.deliver(envelope)
    assert envelope.skipped == 0
    assert envelope.delivered == 1

    context.hass.services.async_call.assert_has_calls(  # type: ignore
        [
            call(
                "switch",
                "turn_on",
                service_data={},
                target={"entity_id": "switch.bell_1"},
                blocking=False,
                context=None,
                return_response=False,
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
                blocking=False,
                context=None,
                target=None,
                return_response=False,
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.living_room"},
                service_data={
                    "media_content_id": "boing_01",
                    "media_content_type": "sound",
                },
                blocking=False,
                context=None,
                return_response=False,
            ),
            call(
                "siren",
                "turn_on",
                target={"entity_id": "siren.lobby"},
                service_data={"data": {"duration": 10, "volume_level": 1, "tone": "boing_01"}},
                blocking=False,
                context=None,
                return_response=False,
            ),
            call(
                "alexa_devices",
                "send_sound",
                service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "boing_01"},
                blocking=False,
                context=None,
                target=None,
                return_response=False,
            ),
        ],
        any_order=False,
    )
    assert len(envelope.calls) == 5


async def test_deliver_alias() -> None:
    """Test on_notify_chime"""
    context = TestingContext(
        transport_configs={
            TRANSPORT_CHIME: {
                "delivery_defaults": {
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
            }
        },
        deliveries={"chimes": {CONF_TRANSPORT: TRANSPORT_CHIME, CONF_DATA: {"chime_tune": "doorbell"}}},
    )

    await context.test_initialize()
    uut = context.transport(TRANSPORT_CHIME)

    envelope: Envelope = Envelope(
        Delivery("chimes", context.delivery_config("chimes"), uut), Notification(context, message="for script only")
    )
    await uut.deliver(envelope)
    assert envelope.skipped == 0
    assert envelope.errored == 0
    assert envelope.delivered == 1

    context.hass.services.async_call.assert_has_calls(  # type: ignore
        [
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.hall_echo"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "home/amzn_sfx_doorbell_chime_01",
                },
                blocking=False,
                context=None,
                return_response=False,
            ),
            call(
                "switch",
                "turn_on",
                service_data={},
                target={"entity_id": "switch.chime_ding_dong"},
                blocking=False,
                context=None,
                return_response=False,
            ),
            call(
                "alexa_devices",
                "send_sound",
                service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "bell01"},
                blocking=False,
                context=None,
                target=None,
                return_response=False,
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.kitchen_alexa"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "home/amzn_sfx_doorbell_chime_02",
                },
                blocking=False,
                context=None,
                return_response=False,
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
                blocking=False,
                context=None,
                target=None,
                return_response=False,
            ),
        ],
        any_order=True,
    )
    assert len(envelope.calls) == 5


class MockGroup:
    def __init__(self, entities: list[str]) -> None:
        self.attributes = {ATTR_ENTITY_ID: entities}


async def test_deliver_to_group() -> None:
    """Test on_notify_chime"""
    context = TestingContext(
        deliveries={
            "chimes": {
                CONF_TRANSPORT: TRANSPORT_CHIME,
                CONF_DATA: {"chime_tune": "dive_dive_dive"},
            }
        },
        entities={
            "group.alexa": MockGroup(["media_player.alexa_1", "media_player.alexa_2"]),
            "group.chime": MockGroup(["switch.bell_1"]),
        },
    )

    uut = ChimeTransport(context, {CONF_DEVICE_DISCOVERY: True})
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("chimes", context.delivery_config("chimes"), uut),
            Notification(context),
            target=Target(["group.alexa", "group.chime", "script.siren_2"]),
        )
    )
    context.hass.services.async_call.assert_has_calls(  # type: ignore
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
                blocking=False,
                context=None,
                target=None,
                return_response=False,
            ),
            call(
                "switch",
                "turn_on",
                service_data={},
                target={"entity_id": "switch.bell_1"},
                blocking=False,
                context=None,
                return_response=False,
            ),
            call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.alexa_1"},
                service_data={
                    "media_content_type": "sound",
                    "media_content_id": "dive_dive_dive",
                },
                blocking=False,
                context=None,
                return_response=False,
            ),
        ],
        any_order=True,
    )


async def test_deliver_rest_command() -> None:
    context = TestingContext(
        transport_configs={
            TRANSPORT_CHIME: {
                "delivery_defaults": {
                    "options": {
                        "chime_aliases": {
                            "siren": {
                                "alexa_devices": "amzn_sfx_trumpet_bugle_04",
                                "switch": {"target": "switch.chime_sax"},
                                "rest_command": {
                                    "target": "rest_command.camera_siren",
                                    "data": {"alarm_code": "11"},
                                },
                            }
                        }
                    },
                },
            }
        },
        deliveries={"siren": {CONF_TRANSPORT: TRANSPORT_CHIME, CONF_DATA: {"chime_tune": "siren"}}},
        services={"rest_command": ["camera_siren"], "alexa_devices": ["send_sound"], "switch": ["turn_on"]},
    )

    await context.test_initialize()
    uut = context.transport("chime")
    await uut.initialize()

    await uut.deliver(
        Envelope(
            context.delivery("siren"),
            Notification(context),
        )
    )
    context.hass.services.async_call.assert_has_calls(  # ty:ignore[possibly-missing-attribute]
        [  # type: ignore
            call(
                "rest_command",
                "camera_siren",
                service_data={"alarm_code": "11"},
                blocking=False,
                context=None,
                return_response=False,
                target=None,
            )
        ],
        any_order=True,
    )
