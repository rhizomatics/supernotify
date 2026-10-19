from __future__ import annotations

from pathlib import Path
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


@pytest.fixture
async def smart_villa(hass: HomeAssistant) -> AsyncGenerator[House]:
    """This house has a richer Home Assistant setup, and Supernotify configured with YAML, from
    smart_villa.yaml alongside this file, which is where its scenarios will go too.

        - 3 floors, with 7 rooms defined
        - 3 Mobile apps
        - No Person entries, only User accounts
        - 2 cameras
        - 2 PIRs
        - A doorbell chime delivery, ringing a hall chime switch and the gate siren

    """

    areas: dict[str, str | None] = {
        "hall": "ground",
        "kitchen": "ground",
        "lounge": "ground",
        "master_bedroom": "first",
        "guest_suite": "first",
        "cinema": "basement",
        "pool_house": None,
    }
    house = House(
        floors=["basement", "ground", "first"],
        areas=areas,
        users={"carla": "carla", "dev": "dev", "nonna": "nonna"},
        android_apps={"dev_phone": "dev"},
        apple_apps={"carla_phone": "carla", "nonna_tablet": "nonna"},
        cameras={"gate": None, "pool": "pool_house"},
        pirs={"hall_pir": "hall", "pool_pir": "pool_house"},
        config=(Path(__file__).parent / "smart_villa.yaml").read_text(),
        stub_actions=["switch.turn_on", "siren.turn_on"],
    )
    await house.setup(hass)
    try:
        yield house
    finally:
        house.cleanup()
