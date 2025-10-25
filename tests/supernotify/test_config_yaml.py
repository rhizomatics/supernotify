"""Config file loading tests"""

import json
import pathlib
from typing import Any, cast
from unittest.mock import patch

from homeassistant import config as hass_config
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_PLATFORM, SERVICE_RELOAD
from homeassistant.core import HomeAssistant, ServiceResponse
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN, SCENARIO_DEFAULT
from custom_components.supernotify import SUPERNOTIFY_SCHEMA as PLATFORM_SCHEMA

FIXTURE = pathlib.Path(__file__).parent.joinpath("..", "..", "examples", "maximal.yaml")


SIMPLE_CONFIG = {
    "name": DOMAIN,
    "platform": DOMAIN,
    "delivery": {
        "testing": {"method": "generic", "action": "notify.send_message"},
        "chime_person": {"method": "chime", "selection": "scenario", "data": {"chime_tune": "person"}},
    },
    "archive": {"enabled": True},
    "scenarios": {
        "simple": {"delivery_selection": "implicit"},
        "somebody": {"delivery_selection": "explicit", "delivery": {"chime_person": {}}},
    },
    "recipients": [{"person": "person.house_owner", "email": "test@testing.com", "phone_number": "+4497177848484"}],
    "methods": {
        "chime": {
            "default": {
                "target": ["media_player.lobby", "switch.doorbell"],
                "options": {
                    "chime_aliases": {"person": {"media_player": "bell_02", "switch": {"entity_id": "switch.chime_ding"}}}
                },
            }
        }
    },
}


def test_schema() -> None:
    assert PLATFORM_SCHEMA(SIMPLE_CONFIG)


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
    assert len(uut.context.people) == 2

    assert "html_email" in uut.context.deliveries
    assert "backup_mail" in uut.context.deliveries
    assert "backup_mail" not in uut.context.delivery_by_scenario[SCENARIO_DEFAULT]
    assert "text_message" in uut.context.deliveries
    assert "alexa_announce" in uut.context.deliveries
    assert "mobile_push" in uut.context.deliveries
    assert "alexa_show" in uut.context.deliveries
    assert "play_chimes" in uut.context.deliveries
    assert "doorbell_chime_alexa" in uut.context.deliveries
    assert "sleigh_bells" in uut.context.deliveries
    assert "upstairs_siren" in uut.context.deliveries
    assert "expensive_api_call" in uut.context.deliveries
    assert "expensive_api_call" not in uut.context.delivery_by_scenario[SCENARIO_DEFAULT]

    assert len(uut.context.deliveries) == 12


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
    assert notification["_message"] == "unit test 9484"
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
    assert response == {"DEFAULT": ["testing"], "simple": ["testing"], "somebody": ["chime_person"]}

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
    assert len(response["trace"]) == 3
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
    assert notification["_message"] == "unit test 105"
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

    call_record: dict[str, Any] = delivered_chimes[0]["calls"][0]  # type: ignore
    del call_record["elapsed"]
    assert call_record == {
        "domain": "media_player",
        "service": "play_media",
        "action_data": {"entity_id": "media_player.lobby", "media_content_type": "sound", "media_content_id": "bell_02"},
    }
