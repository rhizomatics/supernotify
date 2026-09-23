from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from . import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_town_house_floors_and_areas(hass: HomeAssistant, town_house: House) -> None:
    assert set(town_house.floors) == {"ground", "first"}
    assert town_house.floors["ground"].name == "ground"
    assert town_house.floors["first"].name == "first"

    assert set(town_house.areas) == {"kitchen", "lounge", "garage", "bedroom", "office", "garden"}
    for area in ("kitchen", "lounge", "garage"):
        assert town_house.areas[area].floor_id == town_house.floors["ground"].floor_id
    for area in ("bedroom", "office"):
        assert town_house.areas[area].floor_id == town_house.floors["first"].floor_id
    assert town_house.areas["garden"].floor_id is None


async def test_town_house_alexa_notify_devices(hass: HomeAssistant, town_house: House) -> None:
    entity_registry = er.async_get(hass)
    for area in ("kitchen", "lounge", "garage", "bedroom", "office", "garden"):
        entry = entity_registry.async_get(f"notify.{area}")
        assert entry is not None
        assert entry.area_id == town_house.areas[area].id
        assert hass.states.get(f"notify.{area}").state == "unknown"


async def test_town_house_users_and_persons(hass: HomeAssistant, town_house: House) -> None:
    ha_users = {u.name: u for u in await hass.auth.async_get_users()}
    for account in ("alice", "bob"):
        assert account in ha_users
        assert ha_users[account].id == town_house.user_ids[account]

        person_state = hass.states.get(f"person.{account}")
        assert person_state is not None
        assert person_state.attributes["friendly_name"] == account
        assert person_state.attributes["user_id"] == town_house.user_ids[account]


async def test_town_house_mobile_apps(hass: HomeAssistant, town_house: House) -> None:
    assert hass.services.has_service("notify", "mobile_app_alice_phone")
    assert hass.services.has_service("notify", "mobile_app_bob_phone")

    entity_registry = er.async_get(hass)
    assert entity_registry.async_get("device_tracker.alice_phone") is not None
    assert entity_registry.async_get("device_tracker.bob_phone") is not None

    await hass.services.async_call("notify", "mobile_app_alice_phone", {"message": "hi"}, blocking=True)
    assert town_house.calls_by_domain() == {"notify": 1}


async def test_town_house_cameras_and_pirs(hass: HomeAssistant, town_house: House) -> None:
    entity_registry = er.async_get(hass)

    front_door = entity_registry.async_get("camera.front_door")
    assert front_door is not None
    assert front_door.area_id == town_house.areas["garage"].id
    assert hass.states.get("camera.front_door").state == "idle"

    back_garden = entity_registry.async_get("camera.back_garden")
    assert back_garden is not None
    assert back_garden.area_id is None

    hall_pir = entity_registry.async_get("binary_sensor.hall_pir")
    assert hall_pir is not None
    assert hall_pir.area_id == town_house.areas["lounge"].id
    hall_pir_state = hass.states.get("binary_sensor.hall_pir")
    assert hall_pir_state.state == "off"
    assert hall_pir_state.attributes["device_class"] == "motion"

    garden_pir = entity_registry.async_get("binary_sensor.garden_pir")
    assert garden_pir is not None
    assert garden_pir.area_id is None


async def test_house_user_with_no_person_record(hass: HomeAssistant) -> None:
    """A User-only account (no Person) still gets a real HA user - see the CONF_USER_ID
    recipient support in const.py/people.py, which is what this exercises at the fixture level."""
    house = House(users={"joe": "joe_mctest", "jean": None})
    await house.setup(hass)

    assert hass.states.get("person.joe_mctest") is not None
    assert hass.states.get("person.jean") is None

    ha_users = {u.name: u for u in await hass.auth.async_get_users()}
    assert "joe" in ha_users
    assert "jean" in ha_users
    assert ha_users["jean"].id == house.user_ids["jean"]
