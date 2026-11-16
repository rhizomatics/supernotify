from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.hass_api import HomeAssistantAPI
from tests.components.supernotify.ha_testing import async_fire_time_changed
from tests.components.supernotify.hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .framework import House


async def test_notify_no_targets(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
    """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
    )


async def test_notify_empty_target_list_reaches_no_one(hass: HomeAssistant, town_house: House) -> None:
    """An explicitly empty list is a choice of no targets, so the recipients aren't used by default"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        target: []
    """,
        expected_calls=None,
        expected_entities=None,
    )


async def test_notify_blank_target_still_reaches_default_recipients(hass: HomeAssistant, town_house: House) -> None:
    """A blank entry isn't a choice of no targets, unlike an empty list"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
          - ""
    """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
    )


async def test_notify_empty_delivery_list_uses_no_default_deliveries(hass: HomeAssistant, town_house: House) -> None:
    """An explicitly empty list is a choice of no deliveries, as an empty target list is of no
    targets, so the default deliveries aren't used, leaving only those a scenario turns on"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        delivery: []
    """,
        expected_calls=None,
        expected_entities=None,
    )


async def test_notify_with_camera(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        camera_entity_id: camera.front_door
    """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
        expected_images={"notify": ["camera.front_door"]},
    )


async def test_notify_email_target_does_nothing(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
                message: Tea's up
                target:
                  - joe@house.org
            """,
        expected_calls=None,
        expected_entities=None,
    )


async def test_notify_mobile_app_action_target_goes_to_mobile_push(hass: HomeAssistant, town_house: House) -> None:
    """mobile_push claims `notify.mobile_app_<x>` ahead of the generic notify_entity transport"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        target: notify.mobile_app_bob_phone
    """,
        expected_calls={"notify": ["mobile_app_bob_phone"]},
        expected_entities={},
    )


async def test_notify_mobile_app_action_target_not_sent_twice_to_recipient_device(
    hass: HomeAssistant, town_house: House
) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
          - person.bob
          - notify.mobile_app_bob_phone
    """,
        expected_calls={"notify": ["mobile_app_bob_phone"]},
        expected_entities={},
    )


async def test_notify_targets_ground_floor_alexa_devices(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            floor_id: ground
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={
            "notify": [
                "notify.garage",
                "notify.kitchen",
                "notify.lounge",
            ]
        },
    )


async def test_notify_targets_kitchen_alexa_devices(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            area_id: kitchen
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={
            "notify": [
                "notify.kitchen",
            ]
        },
    )


async def test_notify_targets_floor_and_area(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
            message: Tea's up
            target:
                area_id:
                  - kitchen
                  - shed
                floor_id:
                  - ground
        """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={
            "notify": [
                "notify.kitchen",
                "notify.garage",
                "notify.lounge",
            ]
        },
    )


async def test_notify_targets_floor_and_area_with_default_deliveries_via_own_device(
    hass: HomeAssistant, town_house: House
) -> None:
    """Targeting the integration's own 'SuperNotify' device alongside a real target is a
    request to also apply every default delivery's own target - see HomeAssistantAPI.is_own_device.
    """
    await town_house.assert_e2e(
        f"""
                message: Tea's up
                target:
                    area_id:
                      - kitchen
                      - shed
                    floor_id:
                      - ground
                    device_id:
                      - {town_house.supernotify_device_id()}
            """,
        # the area/floor's Alexa echoes go to alexa_devices, which claims them as its own
        # unique category once the selectors are resolved, and dispatches before mobile_push -
        # see Notification.select_deliveries()'s ordering
        expected_calls={"notify": ["send_message", "mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={
            "notify": [
                "notify.kitchen",
                "notify.garage",
                "notify.lounge",
            ]
        },
    )


async def test_notify_with_ad_hoc_notification_level_action(hass: HomeAssistant, town_house: House) -> None:
    """Tapping the notification opens the uri, as `url` for iOS and `clickAction` for Android"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        data:
          actions:
            - action: POUR
              title: Pour it
            - level: notification
              uri: /lovelace/kitchen
    """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
    )
    sent = {call.service: call.data["data"] for call in town_house.service_calls["notify"]}
    assert sent["mobile_app_alice_phone"]["url"] == "/lovelace/kitchen"
    assert "clickAction" not in sent["mobile_app_alice_phone"]
    assert sent["mobile_app_bob_phone"]["clickAction"] == "/lovelace/kitchen"
    assert "url" not in sent["mobile_app_bob_phone"]
    for data in sent.values():
        assert data["actions"] == [{"action": "POUR", "title": "Pour it"}]


async def test_notify_targets_floor_excluding_area(hass: HomeAssistant, town_house: House) -> None:
    """Home Assistant 2026.11 target exclusions, as produced by the target selector's 'Exclude target'"""
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            floor_id: ground
            exclude:
                area_id: kitchen
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={
            "notify": [
                "notify.garage",
                "notify.lounge",
            ]
        },
    )


async def test_notify_targets_floor_excluding_entity(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            floor_id: ground
            exclude:
                entity_id: notify.garage
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={
            "notify": [
                "notify.kitchen",
                "notify.lounge",
            ]
        },
    )


async def test_notify_targets_people_excluding_person(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            entity_id:
              - person.alice
              - person.bob
            exclude:
                entity_id: person.alice
    """,
        expected_calls={"notify": ["mobile_app_bob_phone"]},
        expected_entities={},
    )


async def test_notify_exclusion_matching_nothing_changes_nothing(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            area_id: kitchen
            exclude:
                area_id: bedroom
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={"notify": ["notify.kitchen"]},
    )


async def test_notify_default_recipients_excluding_person(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
        target:
            exclude:
                entity_id: person.bob
    """,
        expected_calls={"notify": ["mobile_app_alice_phone"]},
        expected_entities={},
    )


async def test_notify_targets_members_of_a_group(hass: HomeAssistant, town_house: House) -> None:
    hass.states.async_set("group.downstairs_speakers", "on", {"entity_id": ["notify.kitchen", "notify.lounge"]})
    await town_house.assert_e2e(
        """
        message: Tea's up
        target: group.downstairs_speakers
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={"notify": ["notify.kitchen", "notify.lounge"]},
    )


async def test_notify_follows_a_re_paired_phone(hass: HomeAssistant, town_house: House) -> None:
    """A phone re-paired under a new name has a new notify action, and its old device and action
    go - once that settles, its owner is notified through the new one"""
    device_registry = dr.async_get(hass)
    old_phone = next(d for d in device_registry.devices if ("mobile_app", "device-id_bob_phone") in d.identifiers)

    register_mobile_app(
        HomeAssistantAPI(hass),
        person="person.bob",
        manufacturer="Cheapo",
        os_name="Android",
        device_name="bob_new_phone",
        user_id=town_house.user_ids["bob"],
    )
    device_registry.async_remove_device(old_phone.id)
    hass.services.async_remove("notify", "mobile_app_bob_phone")

    async def record(call: ServiceCall) -> None:
        town_house.service_calls.setdefault(call.domain, []).append(call)

    hass.services.async_remove("notify", "mobile_app_bob_new_phone")
    hass.services.async_register("notify", "mobile_app_bob_new_phone", record)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
    await hass.async_block_till_done()

    await town_house.assert_e2e(
        """
        message: Tea's up
        target: person.bob
    """,
        expected_calls={"notify": ["mobile_app_bob_new_phone"]},
        expected_entities={},
    )


async def test_snooze_survives_a_restart(hass: HomeAssistant, town_house: House) -> None:
    await hass.services.async_call(DOMAIN, "snooze", {"person": "person.bob", "minutes": 60}, blocking=True)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    await town_house.assert_e2e(
        """
        message: Tea's up
    """,
        expected_calls={"notify": ["mobile_app_alice_phone"]},
        expected_entities={},
    )
