from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .framework import House


async def test_notify_no_targets(hass: HomeAssistant, smart_villa: House) -> None:
    await smart_villa.assert_e2e(
        """
        message: Dinner on the terrace
    """,
        expected_calls={"notify": ["mobile_app_carla_phone", "mobile_app_dev_phone", "mobile_app_nonna_tablet"]},
        expected_entities={},
    )


async def test_doorbell_chime_from_yaml_delivery(hass: HomeAssistant, smart_villa: House) -> None:
    await smart_villa.assert_e2e(
        """
        message: Someone at the gate
        delivery: doorbell_chime
    """,
        expected_calls={"switch": ["turn_on"], "siren": ["turn_on"]},
        expected_entities={"switch": ["switch.hall_chime"], "siren": ["siren.gate"]},
    )
