from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
from . import House


@pytest.fixture
async def town_house(hass: HomeAssistant) -> House:
    """This house has a minimal Home Assistant setup, with no technical
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
        mobile_apps={"alice_phone": "alice", "bob_phone": "bob"},
        cameras={"front_door": "garage", "back_garden": None},
        pirs={"hall_pir": "lounge", "garden_pir": None},
    )
    await house.setup(hass)
    return house
