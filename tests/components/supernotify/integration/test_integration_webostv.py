"""End to end flows to LG webOS TVs, found with no YAML and targeted by area or floor"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from tests.components.supernotify.ha_testing import MockConfigEntry

from .framework import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# TV config entry title -> area
TVS: dict[str, str] = {"Lounge TV": "lounge", "Bedroom TV": "bedroom"}


async def webos_house(hass: HomeAssistant, bedroom_tv_state: str = "on") -> House:
    entries: dict[str, MockConfigEntry] = {}
    for title in TVS:
        entries[title] = MockConfigEntry(domain="webostv", title=title, data={})
        entries[title].add_to_hass(hass)
    house = House(
        floors=["ground", "first"],
        areas={"lounge": "ground", "kitchen": "ground", "bedroom": "first"},
        alexa_per_area=False,
        stub_actions=["notify.lounge_tv", "notify.bedroom_tv"],
    )
    await house.setup(hass)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    for title, area in TVS.items():
        object_id = title.lower().replace(" ", "_")
        # as the integration sets a TV up, the area is on its device, not the entity
        device = device_registry.async_get_or_create(
            config_entry_id=entries[title].entry_id, identifiers={("webostv", object_id)}, name=title
        )
        device_registry.async_update_device(device.id, area_id=house.areas[area].id)
        tv = entity_registry.async_get_or_create(
            "media_player",
            "webostv",
            f"{object_id}_id",
            suggested_object_id=object_id,
            config_entry=entries[title],
            device_id=device.id,
        )
        hass.states.async_set(tv.entity_id, bedroom_tv_state if area == "bedroom" else "on")
    return house


async def test_area_target_reaches_its_tv(hass: HomeAssistant) -> None:
    house = await webos_house(hass)
    await house.assert_e2e(
        """
        message: Dinner is ready
        target:
            area_id: lounge
    """,
        expected_calls={"notify": ["lounge_tv"]},
    )
    assert house.service_calls["notify"][0].data == {"message": "Dinner is ready"}


async def test_area_without_tv_reaches_none(hass: HomeAssistant) -> None:
    house = await webos_house(hass)
    await house.assert_e2e(
        """
        message: Dinner is ready
        target:
            area_id: kitchen
    """,
        expected_calls=None,
    )


async def test_floor_target_reaches_tvs_on_it(hass: HomeAssistant) -> None:
    house = await webos_house(hass)
    await house.assert_e2e(
        """
        message: Bedtime
        target:
            floor_id:
              - ground
              - first
    """,
        expected_calls={"notify": ["lounge_tv", "bedroom_tv"]},
    )


async def test_tv_that_is_off_is_skipped(hass: HomeAssistant) -> None:
    house = await webos_house(hass, bedroom_tv_state="off")
    await house.assert_e2e(
        """
        message: Bedtime
        target:
            floor_id:
              - ground
              - first
    """,
        expected_calls={"notify": ["lounge_tv"]},
    )


async def test_untargeted_notification_leaves_tvs_alone(hass: HomeAssistant) -> None:
    house = await webos_house(hass)
    await house.assert_e2e(
        """
        message: Bedtime
    """,
        expected_calls=None,
    )
