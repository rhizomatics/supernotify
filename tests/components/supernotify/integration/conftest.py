from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.area_registry import AreaEntry
from homeassistant.helpers.floor_registry import FloorEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
from . import House


@pytest.fixture
async def town_house(hass: HomeAssistant) -> House:
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    floors: dict[int, FloorEntry] = {0: floor_registry.async_create("Ground"), 1: floor_registry.async_create("First")}
    areas: dict[str, AreaEntry] = {
        "kitchen": area_registry.async_create("Kitchen", floor_id=floors[0].floor_id),
        "lounge": area_registry.async_create(name="Lounge", floor_id=floors[0].floor_id),
        "garage": area_registry.async_create(name="Garage", floor_id=floors[0].floor_id),
        "bedroom": area_registry.async_create(name="Bedroom", floor_id=floors[1].floor_id),
        "office": area_registry.async_create(name="Office", floor_id=floors[1].floor_id),
    }
    house = House(floors, areas)
    await house.setup(hass)
    return house
