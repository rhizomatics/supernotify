from typing import cast

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify import CONF_DATA, CONF_DEBUG, CONF_DEVICE_DISCOVERY, CONF_TRANSPORT, TRANSPORT_CHIME
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.chime import ChimeTransport

from .doubles_lib import service_call
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
            service_call("switch", "turn_on", target={"entity_id": "switch.bell_1"}),
            service_call(
                "script",
                "turn_on",
                target={"entity_id": "script.alarm_2"},
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
            service_call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.living_room"},
                service_data={
                    "media": {
                        "media_content_id": "boing_01",
                        "media_content_type": "sound",
                    }
                },
            ),
            service_call(
                "siren",
                "turn_on",
                target={"entity_id": "siren.lobby"},
                service_data={"data": {"duration": 10, "volume_level": 1, "tone": "boing_01"}},
            ),
            service_call(
                "alexa_devices",
                "send_sound",
                service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "boing_01"},
            ),
        ],
        any_order=False,
    )
    assert len(envelope.calls) == 5


async def test_deliver_alias() -> None:
    """Test on_notify_chime"""
    context = TestingContext(
        transports={
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
                                    "data": {"visitor_name": "Guest"},
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
            service_call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.hall_echo"},
                service_data={
                    "media": {
                        "media_content_type": "sound",
                        "media_content_id": "home/amzn_sfx_doorbell_chime_01",
                    }
                },
            ),
            service_call("switch", "turn_on", target={"entity_id": "switch.chime_ding_dong"}),
            service_call(
                "alexa_devices",
                "send_sound",
                service_data={"device_id": "ffff0000eeee1111dddd2222cccc3333", "sound": "bell01"},
            ),
            service_call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.kitchen_alexa"},
                service_data={"media": {"media_content_type": "sound", "media_content_id": "home/amzn_sfx_doorbell_chime_02"}},
            ),
            service_call(
                "script",
                "turn_on",
                target={"entity_id": "script.front_door_bell"},
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


async def test_script_debug() -> None:
    context = TestingContext(
        transports={
            TRANSPORT_CHIME: {
                "delivery_defaults": {
                    "options": {
                        "chime_aliases": {
                            "doorbell": {
                                "script": {
                                    "target": "script.front_door_bell",
                                    "data": {"visitor_name": "Guest"},
                                },
                            }
                        }
                    },
                },
            }
        },
        deliveries={"chimes": {CONF_TRANSPORT: TRANSPORT_CHIME, CONF_DEBUG: True, CONF_DATA: {"chime_tune": "doorbell"}}},
    )

    await context.test_initialize()
    uut = context.transport(TRANSPORT_CHIME)

    envelope: Envelope = Envelope(
        Delivery("chimes", context.delivery_config("chimes"), uut), Notification(context, message="for script only")
    )
    await uut.deliver(envelope)

    context.hass.services.async_call.assert_has_calls(
        [  # type: ignore
            service_call(
                "script",
                "turn_on",
                service_data={
                    "variables": {
                        "visitor_name": "Guest",
                        "message": "for script only",
                        "title": None,
                        "priority": "medium",
                        "chime_tune": "doorbell",
                        "chime_volume": None,
                        "chime_duration": None,
                    },
                    "wait": True,
                },
                blocking=True,
                return_response=True,
                target={"entity_id": "script.front_door_bell"},
            )
        ],
        any_order=True,
    )


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
            service_call(
                "script",
                "turn_on",
                target={"entity_id": "script.siren_2"},
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
            service_call("switch", "turn_on", target={"entity_id": "switch.bell_1"}),
            service_call(
                "media_player",
                "play_media",
                target={"entity_id": "media_player.alexa_1"},
                service_data={
                    "media": {
                        "media_content_type": "sound",
                        "media_content_id": "dive_dive_dive",
                    }
                },
            ),
        ],
        any_order=True,
    )


async def test_deliver_rest_command() -> None:
    context = TestingContext(
        transports={
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
                                "rest_command_alt_1": {
                                    "domain": "rest_command",
                                    "target": "invalid_target_id",
                                },
                                "rest_command_alt_2": {
                                    "target": "rest_command.valid_target_id",
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
    assert context.hass.services.async_call.call_count == 3
    context.hass.services.async_call.assert_has_calls(  # ty:ignore[possibly-missing-attribute]
        [
            service_call("switch", "turn_on", target={"entity_id": "switch.chime_sax"}),
            service_call("rest_command", "camera_siren", service_data={"alarm_code": "11"}),
            service_call("rest_command", "valid_target_id"),
        ],
        any_order=True,
    )


async def test_documentation_example() -> None:
    context = TestingContext(
        transports="""
  chime:
    device_discovery: True
    device_model_include: Speaker Group
    delivery_defaults:
        target:
        - media_player.kitchen_echo
        - media_player.bedroom
        - ffff0000eeee1111dddd2222cccc3333 # Alexa Devices device_id
        options:
            chime_aliases:
                doorbell: #alias
                    alexa_devices: # integration domain or label ( if label then domain must be a key in the config )
                        tune: amzn_sfx_cat_meow_1x_01
                    media_player:
                        # resolves to media_player/play_media with sound configured for this path
                        tune: home/amzn_sfx_doorbell_chime_02
                        # entity_id list defaults to `target` of transport default or action call
                        # this entry can also be shortcut as `media_player: home/amzn_sfx_doorbell_chime_02`
                    media_player_alt:
                        # Not all the media players are Amazon Alexa based, so override for other flavours
                        tune: raindrops_and_roses.mp4
                        target:
                            - media_player.hall_custom # domain inferred from target
                    switch:
                        # resolves to switch/turn_on with entity id switch.ding_dong
                        target: switch.chime_ding_dong
                    siren_except_bedroom:
                        # resolves to siren/turn_on with tune bleep and default volume/duration
                        tune: bleep
                        domain: siren # domain must be explicit since key is label not domain and no explicit targets
                    siren_bedroom:
                        alias: Short and quiet burst for just the bedroom siren
                        domain: siren
                        tune: bleep
                        target: siren.bedroom
                        volume: 0.1
                        duration: 5
                    script:
                        alias: Run a Home Assistant script defined elsewhere in config
                        target: script.pull_bell_cord
                        data:
                            duration: 25
                    rest_command:
                        alias: call a rest api passing data to the templated URL
                        target: rest_command.api_call_to_camera_alarm
                        data:
                            alarm_tone: 14

                red_alert:
                    # non-dict defaults to a dict with a single key `tune`
                    alexa_devices: scifi/amzn_sfx_scifi_alarm_04
                    siren: emergency
                    media_player:
                    # tune defaults to alias ('red_alert')
"""
    )
    await context.test_initialize()
    uut: ChimeTransport = cast("ChimeTransport", context.transport("chime"))
    await uut.initialize()

    assert len(uut.chime_aliases) == 2
    doorbell = uut.chime_aliases["doorbell"]
    assert len(doorbell) == 8
    assert sum(1 for c in doorbell.values() if c.get("domain") or c.get("target")) == 8

    assert doorbell["alexa_devices"] == {"tune": "amzn_sfx_cat_meow_1x_01", "domain": "alexa_devices"}
    assert doorbell["media_player"] == {"tune": "home/amzn_sfx_doorbell_chime_02", "domain": "media_player"}
    assert doorbell["media_player_alt"]["tune"] == "raindrops_and_roses.mp4"
    assert "domain" not in doorbell["media_player_alt"]  # not a valid domain
    assert doorbell["media_player_alt"]["target"].entity_ids == ["media_player.hall_custom"]
    assert doorbell["switch"]["target"].entity_ids == ["switch.chime_ding_dong"]
    assert doorbell["switch"]["domain"] == "switch"
    assert doorbell["siren_except_bedroom"]["tune"] == "bleep"
    assert doorbell["siren_except_bedroom"]["domain"] == "siren"
    assert doorbell["rest_command"]["target"].entity_ids == ["rest_command.api_call_to_camera_alarm"]
    assert doorbell["rest_command"]["data"] == {"alarm_tone": 14}
    assert doorbell["script"]["target"].entity_ids == ["script.pull_bell_cord"]
    assert doorbell["script"]["data"] == {"duration": 25}
    assert doorbell["siren_bedroom"]["alias"] == "Short and quiet burst for just the bedroom siren"
    assert doorbell["siren_bedroom"]["target"].entity_ids == ["siren.bedroom"]
    assert doorbell["siren_bedroom"]["volume"] == 0.1
    assert doorbell["siren_bedroom"]["domain"] == "siren"

    red_alert = uut.chime_aliases["red_alert"]
    assert len(red_alert) == 3
    assert sum(1 for c in red_alert.values() if c["domain"]) == 3
    assert red_alert["media_player"] == {"tune": "red_alert", "domain": "media_player"}
    assert red_alert["siren"] == {"tune": "emergency", "domain": "siren"}
    assert red_alert["alexa_devices"] == {"tune": "scifi/amzn_sfx_scifi_alarm_04", "domain": "alexa_devices"}
