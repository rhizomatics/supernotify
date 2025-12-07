"""Config file loading tests"""

import json
import pathlib
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import ATTR_AREA_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID, CONF_PLATFORM, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify import SUPERNOTIFY_SCHEMA as PLATFORM_SCHEMA
from custom_components.supernotify.model import Target

if TYPE_CHECKING:
    from homeassistant.util.json import JsonObjectType

FIXTURE = pathlib.Path(__file__).parent.joinpath("..", "..", "examples", "maximal.yaml")


SIMPLE_CONFIG = {
    "name": DOMAIN,
    "platform": DOMAIN,
    "delivery": {
        "testing": {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"},
        "plain_email": {"transport": "email"},
        "chime_person": {"transport": "chime", "selection": ["scenario", "fallback"], "data": {"chime_tune": "person"}},
    },
    "archive": {"enabled": True},
    "scenarios": {
        "simple": {"delivery_selection": "implicit"},
        "somebody": {"delivery_selection": "explicit", "delivery": {"chime_person": {}}},
    },
    "recipients": [
        {
            "person": "person.house_owner",
            "email": "test@testing.com",
            "phone_number": "+4497177848484",
            "delivery": {"chime": {"target": "switch.office_bell", "data": {"volume": "whisper"}}},
            "target": {"discord": "@mickey", "telegram": "mickey.mouse", "812Mhz": ["039392", "84834"]},
        }
    ],
    "transports": {
        "chime": {
            "delivery_defaults": {
                "target": ["media_player.lobby", "switch.doorbell"],
                "options": {
                    "chime_aliases": {"person": {"media_player": "bell_02", "switch": {"target": "switch.chime_ding"}}}
                },
            }
        },
        "email": {"enabled": False, "delivery_defaults": {"action": "notify.smtp"}},
    },
}


def test_schema() -> None:
    assert PLATFORM_SCHEMA(SIMPLE_CONFIG)


async def test_transport_setup(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    assert hass.states.get("supernotify.transport_chime").state == "on"  # type: ignore
    assert hass.states.get("supernotify.transport_generic").state == "on"  # type: ignore
    assert hass.states.get("supernotify.transport_email").state == "off"
    assert hass.states.get("supernotify.delivery_plain_email").state == "off"
    assert hass.states.get("supernotify.delivery_testing").state == "on"  # type: ignore


async def test_reload(hass: HomeAssistant) -> None:
    hass.states.async_set("alarm_control_panel.home_alarm_control", "")

    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})

    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)

    with patch.object(hass_config, "YAML_CONFIG_FILE", FIXTURE):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert not hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    uut = hass.data["notify_services"][DOMAIN][0]
    assert len(uut.context.people_registry.people) == 2

    assert "DEFAULT_notify_entity" in uut.context.delivery_registry.deliveries
    assert "html_email" in uut.context.delivery_registry.deliveries
    assert "backup_mail" in uut.context.delivery_registry.deliveries
    assert "backup_mail" not in [d.name for d in uut.context.delivery_registry.implicit_deliveries]
    assert "text_message" in uut.context.delivery_registry.deliveries
    assert "alexa_announce" in uut.context.delivery_registry.deliveries
    assert "mobile_push" in uut.context.delivery_registry.deliveries
    assert "alexa_show" in uut.context.delivery_registry.deliveries
    assert "play_chimes" in uut.context.delivery_registry.deliveries
    assert "doorbell_chime_alexa" in uut.context.delivery_registry.deliveries
    assert "sleigh_bells" in uut.context.delivery_registry.deliveries
    assert "upstairs_siren" in uut.context.delivery_registry.deliveries
    assert "my_hw_notifiers" in uut.context.delivery_registry.deliveries
    assert uut.context.delivery_registry.deliveries["my_hw_notifiers"].target == Target({
        ATTR_FLOOR_ID: ["ground"],
        ATTR_LABEL_ID: ["433sounder"],
        ATTR_AREA_ID: ["backyard"],
    })
    assert "expensive_api_call" in uut.context.delivery_registry.deliveries
    assert "expensive_api_call" not in [d.name for d in uut.context.delivery_registry.implicit_deliveries]

    assert len(uut.context.delivery_registry.deliveries) == 14


async def test_call_action(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})

    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {"title": "my title", "message": "unit test 9484", "data": {"delivery": {"testing": None}}},
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    assert notification is not None
    assert notification["delivered_envelopes"][0]["message"] == "unit test 9484"
    assert notification["priority"] == "medium"


async def test_empty_config(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"name": DOMAIN, "platform": DOMAIN},
            ]
        },
    )

    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(NOTIFY_DOMAIN, DOMAIN, {"title": "my title", "message": "unit test"}, blocking=True)
    notification: JsonObjectType | None = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert notification is not None


async def test_empty_config_delivers_to_notify_entities(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass,
        NOTIFY_DOMAIN,
        {
            NOTIFY_DOMAIN: [
                {"name": DOMAIN, "platform": DOMAIN},
            ]
        },
    )
    assert await async_setup_component(
        hass, "file", {"file": [{"platform": "notify", "name": "notilog", "filepath": "notify.log"}]}
    )

    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN, DOMAIN, {"title": "my title", "message": "unit test", "target": ["notify.notilog"]}, blocking=True
    )
    notification: JsonObjectType | None = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert notification is not None
    assert len(notification["delivered_envelopes"]) == 1  # type: ignore[arg-type]
    assert len(notification["undelivered_envelopes"]) == 0  # type: ignore[arg-type]

    await hass.services.async_call(NOTIFY_DOMAIN, DOMAIN, {"title": "my title", "message": "unit test"}, blocking=True)
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert notification is not None
    assert len(notification["delivered_envelopes"]) == 0  # type: ignore[arg-type]
    assert len(notification["undelivered_envelopes"]) == 0  # type: ignore[arg-type]


async def test_exposed_scenario_events(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    hass.states.async_set("supernotify.scenario_simple", "off")
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        "supernotify", "enquire_deliveries_by_scenario", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"somebody": ["chime_person"]}
    hass.states.async_set("supernotify.scenario_simple", "on")
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        "supernotify", "enquire_deliveries_by_scenario", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"simple": ["testing", "DEFAULT_mobile_push", "DEFAULT_notify_entity"], "somebody": ["chime_person"]}


async def test_exposed_delivery_events(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    hass.states.async_set("supernotify.delivery_testing", "off")
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        "supernotify", "enquire_deliveries_by_scenario", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"simple": ["DEFAULT_mobile_push", "DEFAULT_notify_entity"], "somebody": ["chime_person"]}
    hass.states.async_set("supernotify.delivery_testing", "on")
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        "supernotify", "enquire_deliveries_by_scenario", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"simple": ["testing", "DEFAULT_mobile_push", "DEFAULT_notify_entity"], "somebody": ["chime_person"]}


async def test_exposed_recipients(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    hass.states.async_set("supernotify.recipient_house_owner", "off")
    await hass.async_block_till_done()
    response = await hass.services.async_call("supernotify", "enquire_recipients", None, blocking=True, return_response=True)
    await hass.async_block_till_done()
    expected_response: dict[str, Any] = {
        "recipients": [
            {
                "person": "person.house_owner",
                "alias": None,
                "enabled": False,
                "state": None,
                "email": "test@testing.com",
                "phone_number": "+4497177848484",
                "user_id": None,
                "mobile_discovery": True,
                "mobile_devices": [],
                "delivery": {
                    "chime": {"target": {"entity_id": ["switch.office_bell"]}, "enabled": True, "data": {"volume": "whisper"}}
                },
                "target": {
                    "discord": ["@mickey"],
                    "telegram": ["mickey.mouse"],
                    "812Mhz": ["039392", "84834"],
                    "person_id": ["person.house_owner"],
                    "email": ["test@testing.com"],
                    "phone": ["+4497177848484"],
                },
            }
        ]
    }
    assert response == expected_response
    hass.states.async_set("supernotify.recipient_house_owner", "on")
    await hass.async_block_till_done()
    response = await hass.services.async_call("supernotify", "enquire_recipients", None, blocking=True, return_response=True)
    await hass.async_block_till_done()
    expected_response["recipients"][0]["enabled"] = True
    assert response == expected_response


async def test_exposed_transport_events(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    assert await async_setup_component(hass, "media_player", {"media_player": {CONF_PLATFORM: "test"}})
    assert await async_setup_component(hass, "switch", {"switch": {CONF_PLATFORM: "test"}})
    assert await async_setup_component(hass, "notify", {"notify": [{CONF_PLATFORM: "test"}]})
    await hass.async_block_till_done()

    hass.states.async_set("supernotify.transport_generic", "off")
    await hass.async_block_till_done()
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {"title": "my title", "message": "unit test 9001a", "data": {"delivery": ["testing", "chime_person"]}},
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert notification is not None
    assert len(notification["delivered_envelopes"]) == 1  # type: ignore[arg-type]
    # type: ignore
    assert notification["delivered_envelopes"][0]["delivery_name"] == "chime_person"
    assert len(notification["undelivered_envelopes"]) == 0  # type: ignore[arg-type]

    hass.states.async_set("supernotify.transport_generic", "on")
    await hass.async_block_till_done()
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {"title": "my title", "message": "unit test 9001b", "data": {"delivery": ["testing", "chime_person"]}},
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert notification is not None
    assert len(notification["delivered_envelopes"]) == 2  # type: ignore
    assert len(notification["undelivered_envelopes"]) == 0  # type: ignore


async def test_call_supplemental_actions(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    response: ServiceResponse = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {}

    response = await hass.services.async_call(
        "supernotify", "enquire_deliveries_by_scenario", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"simple": ["testing", "DEFAULT_mobile_push", "DEFAULT_notify_entity"], "somebody": ["chime_person"]}

    response = await hass.services.async_call(
        "supernotify", "enquire_active_scenarios", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response == {"scenarios": []}
    json.dumps(response)

    response = await hass.services.async_call(
        "supernotify", "enquire_active_scenarios", {"trace": True}, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response
    assert isinstance(response["scenarios"], list)
    assert "trace" in response
    assert isinstance(response["trace"], tuple)
    assert len(response["trace"]) == 3  # type: ignore
    enabled, disabled, cvars = response["trace"]
    assert isinstance(enabled, list)
    assert isinstance(disabled, list)
    assert isinstance(cvars, dict)
    assert [s["name"] for s in disabled] == ["simple", "somebody"]
    assert enabled == []
    assert cvars["notification_priority"] == "medium"
    json.dumps(response)

    response = await hass.services.async_call("supernotify", "purge_archive", None, blocking=True, return_response=True)
    await hass.async_block_till_done()
    assert response is not None
    assert "purged" in response
    assert cast("int", response["purged"]) >= 0
    json.dumps(response)


async def test_template_delivery(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    await async_call_from_config(
        hass,
        {
            "service": "notify.supernotify",
            "data_template": """{
                                "title": "my title",
                                "message": "unit test {{ 100+5 }}",
                                "data": {
                                    "priority": "{% if 3>5 %}low{% else %}high{%endif%}",
                                    "delivery": {"email": {"data": {"footer": ""}}}}
                            }""",
        },
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    assert notification is not None
    assert notification["delivered_envelopes"][0]["message"] == "unit test 105"
    assert notification["priority"] == "high"


async def test_delivery_and_scenario(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    assert await async_setup_component(hass, "media_player", {"media_player": {CONF_PLATFORM: "test"}})
    assert await async_setup_component(hass, "switch", {"switch": {CONF_PLATFORM: "test"}})
    assert await async_setup_component(hass, "notify", {"notify": [{CONF_PLATFORM: "test"}]})
    await hass.async_block_till_done()
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {"title": "my title", "message": "unit test 85753", "data": {"apply_scenarios": ["somebody"]}},
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    assert notification is not None
    assert isinstance(notification["delivered_envelopes"], list)

    delivered_chimes = [
        e
        for e in notification["delivered_envelopes"]
        if e and isinstance(e, dict) and e.get("delivery_name", "") == "chime_person"
    ]
    assert len(delivered_chimes) == 1

    # type: ignore
    call_record: dict[str, Any] = delivered_chimes[0]["calls"][0]
    del call_record["elapsed"]
    assert call_record == {
        "domain": "media_player",
        "action": "play_media",
        "action_data": {"media_content_type": "sound", "media_content_id": "bell_02"},
        "target_data": {"entity_id": "media_player.lobby"},
        "debug": False,
    }


async def test_recipients_configured(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [SIMPLE_CONFIG]})
    await hass.async_block_till_done()
    response: ServiceResponse = await hass.services.async_call(
        "supernotify", "enquire_recipients", None, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response is not None
    assert "recipients" in response
    assert isinstance(response, dict)
    assert len(response["recipients"]) == 1  # type: ignore
    assert isinstance(response["recipients"], list)

    assert response["recipients"][0] == {
        "person": "person.house_owner",
        "alias": None,
        "enabled": True,
        "state": None,
        "email": "test@testing.com",
        "phone_number": "+4497177848484",
        "user_id": None,
        "mobile_discovery": True,
        "mobile_devices": [],
        "delivery": {
            "chime": {"target": {"entity_id": ["switch.office_bell"]}, "data": {"volume": "whisper"}, "enabled": True}
        },
        "target": {
            "discord": ["@mickey"],
            "telegram": ["mickey.mouse"],
            "812Mhz": ["039392", "84834"],
            "email": ["test@testing.com"],
            "phone": ["+4497177848484"],
            "person_id": ["person.house_owner"],
        },
    }
