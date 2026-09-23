from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import House


async def test_notify_no_targets(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Tea's up
    """)

    assert town_house.calls_by_domain() == {"notify": 2}
    assert town_house.entity_ids_called("notify") == []
    assert town_house.services_called("notify") == ["mobile_app_alice_phone", "mobile_app_bob_phone"]


async def test_notify_targets_ground_floor_alexa_devices(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Kettle's boiled
        target:
            floor_id: ground
    """)

    assert town_house.calls_by_domain() == {"notify": 1}
    assert town_house.services_called("notify") == ["send_message"]
    assert town_house.entity_ids_called("notify") == [
        "notify.garage",
        "notify.kitchen",
        "notify.lounge",
    ]


async def test_notify_targets_kitchen_alexa_devices(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Kettle's boiled
        target:
            area_id: kitchen
    """)

    assert town_house.calls_by_domain() == {"notify": 1}
    assert town_house.services_called("notify") == ["send_message"]
    assert town_house.entity_ids_called("notify") == [
        "notify.kitchen",
    ]


async def test_notify_targets_floor_and_area(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Kettle's boiled
        target:
            area_id:
              - kitchen
              - shed
            floor_id:
              - ground
    """)

    assert town_house.calls_by_domain() == {"notify": 1}
    assert town_house.services_called("notify") == ["send_message"]
    assert town_house.entity_ids_called("notify") == [
        "notify.garage",
        "notify.kitchen",
        "notify.lounge",
    ]


async def test_notify_targets_floor_and_area_with_default_deliveries(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Kettle's boiled
        target:
            area_id:
              - kitchen
              - shed
            floor_id:
              - ground
        delivery:
            mobile_push:
                target:
                  - person.alice
                  - person.bob
    """)

    assert town_house.calls_by_domain() == {"notify": 3}
    assert town_house.entity_ids_called("notify") == [
        "notify.garage",
        "notify.kitchen",
        "notify.lounge",
    ]
    assert town_house.services_called("notify") == ["mobile_app_alice_phone", "mobile_app_bob_phone", "send_message"]


async def test_notify_targets_floor_and_area_with_default_deliveries_via_own_device(
    hass: HomeAssistant, town_house: House
) -> None:
    """Targeting the integration's own 'SuperNotify' device alongside a real target is a
    request to also apply every default delivery's own target - see HomeAssistantAPI.is_own_device.
    """
    await town_house.call(f"""
        message: Kettle's boiled
        target:
            area_id:
              - kitchen
              - shed
            floor_id:
              - ground
            device_id:
              - {town_house.supernotify_device_id()}
    """)

    assert town_house.calls_by_domain() == {"notify": 3}
    assert town_house.entity_ids_called("notify") == [
        "notify.garage",
        "notify.kitchen",
        "notify.lounge",
    ]
    assert town_house.services_called("notify") == ["mobile_app_alice_phone", "mobile_app_bob_phone", "send_message"]
