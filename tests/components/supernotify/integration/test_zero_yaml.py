from __future__ import annotations

import sys
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from conftest import test_image as build_test_image

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
    await town_house.call("""
        message: Tea's up
        camera_entity_id: camera.front_door
    """)

    await town_house.assert_e2e(
        """
            message: Tea's up
            camera_entity_id: camera.front_door
        """,
        expected_calls={"notify": ["mobile_app_alice_phone", "mobile_app_bob_phone"]},
        expected_entities={},
    )

    # both mobile targets get sent the same processed image, referenced by its share path
    # (see MediaStorage.share_path) rather than a filename baked into the assertion, since that
    # name is derived from a fresh notification id each run
    image_urls = {call.data["data"]["image"] for call in town_house.service_calls["notify"]}
    assert len(image_urls) == 1
    (image_url,) = image_urls

    retrieved_image = Image.open(BytesIO(await town_house.image_bytes(image_url)))
    original_image = Image.open(str(build_test_image().path))
    # the camera's raw still is reprocessed (metadata stripped, re-encoded) before sending, so
    # only dimensions - not exact bytes - are expected to survive the round trip
    assert retrieved_image.size == original_image.size


async def test_notify_email_target_does_nothing(hass: HomeAssistant, town_house: House) -> None:
    await town_house.assert_e2e(
        """
                message: Tea's up
                target:
                  - joe@house.org
            """,
        expected_calls={},
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


@pytest.mark.skipif(sys.version_info < (3, 13), reason="Requires Python 3.13 or higher for HA with device loookup")
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
