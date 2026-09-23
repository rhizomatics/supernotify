from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import House


async def test_notify_targets_ground_floor_alexa_devices(hass: HomeAssistant, town_house: House) -> None:
    await town_house.call("""
        message: Kettle's boiled
        target:
            floor_id: ground
    """)

    assert len(town_house.service_calls["notify"]) == 1
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

    assert len(town_house.service_calls["notify"]) == 1
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

    assert len(town_house.service_calls["notify"]) == 1
    assert town_house.entity_ids_called("notify") == [
        "notify.garage",
        "notify.kitchen",
        "notify.lounge",
    ]
