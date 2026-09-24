from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .framework import House


async def test_notify_no_targets(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
        message: Tea's up
    """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
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


@pytest.mark.skipif(sys.version_info < (3, 14), reason="Requires Python 3.13 or higher for HA with device loookup")
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
        expected_calls={"notify": ["send_message", "mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={
            "notify": [
                "notify.kitchen",
                "notify.garage",
                "notify.lounge",
            ]
        },
    )
