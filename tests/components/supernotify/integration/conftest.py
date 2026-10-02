from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from homeassistant.core import HomeAssistant
from .framework import House


@pytest.fixture
async def starter_flat(hass: HomeAssistant) -> AsyncGenerator[House]:
    """This house has a minimal Home Assistant setup, with no technical
    users, and a completely default Supernotify installation with zero YAML.

        - One floor, but not defined in HA, no areas, no labels
        - No Person entries, only 1 User accounts
        - One mobile app

    """

    house = House(
        users={"jo": "jo"},
        apple_apps={"jo_phone": "jo"},
    )
    await house.setup(hass)
    try:
        yield house
    finally:
        house.cleanup()


@pytest.fixture
async def town_house(hass: HomeAssistant) -> AsyncGenerator[House]:
    """This house has a slightly richer Home Assistant setup, with no technical
    users, and a completely default Supernotify installation with zero YAML.

        - 2 floors, with 5 rooms defined
        - Five Alexa echo devices
        - 2 Mobile apps, with just enough config to make them work
        - No Person entries, only User accounts
        - 2 cameras
        - 2 PIRs

    """

    areas: dict[str, str | None] = {
        "kitchen": "ground",
        "lounge": "ground",
        "garage": "ground",
        "bedroom": "first",
        "office": "first",
        "garden": None,
    }
    house = House(
        floors=["ground", "first"],
        areas=areas,
        users={"alice": "alice", "bob": "bob"},
        android_apps={"bob_phone": "bob"},
        apple_apps={"alice_phone": "alice"},
        cameras={"front_door": "garage", "back_garden": None},
        pirs={"hall_pir": "lounge", "garden_pir": None},
    )
    await house.setup(hass)
    try:
        yield house
    finally:
        house.cleanup()
