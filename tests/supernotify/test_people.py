

from homeassistant.components import person
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry

from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.people import PeopleRegistry

from .hass_setup_lib import TestingContext, register_mobile_app


async def test_people_registry_finds_people(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        components={"person": {}}
     )
    await ctx.test_initialize()
    await person.async_create_person(hass, 'Joe McTest')
    await person.async_create_person(hass, 'Mae McTest')

    uut = PeopleRegistry([], ctx.hass_api)
    # only hass_api required, not initialized people registry
    assert uut.find_people() == ["person.joe_mctest", "person.mae_mctest"]


def test_autoresolve_mobile_devices_for_no_devices(hass: HomeAssistant) -> None:
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    uut = PeopleRegistry([], hass_api)
    uut.initialize()
    assert uut.mobile_devices_for_person("person.test_user") == []


def test_autoresolve_mobile_devices_for_devices(
    hass: HomeAssistant,
    device_registry: device_registry.DeviceRegistry,
    entity_registry: entity_registry.EntityRegistry,
) -> None:
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    uut = PeopleRegistry([], hass_api)
    uut.initialize()
    device = register_mobile_app(hass_api, person="person.test_user", device_name="phone_bob", title="Bobs Phone")
    assert device is not None
    assert uut.mobile_devices_for_person("person.test_user") == [
        {
            "manufacturer": "xUnit",
            "model": "PyTest001",
            "mobile_app_id": "mobile_app_bobs_phone",
            "device_tracker": "device_tracker.mobile_app_phone_bob",
            "device_id": device.id,
            "device_name": "Bobs Phone",
            # "device_labels": set(),
        }
    ]


async def test_filter_recipients(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        components={"person": {}}
     )
    await ctx.test_initialize()
    await person.async_create_person(hass, 'Joe McTest')
    await person.async_create_person(hass, 'Mae McTest')
    await hass.async_block_till_done()
    hass.states.async_set("person.joe_mctest", "home")
    hass.states.async_set("person.mae_mctest", "not_home")
    uut = PeopleRegistry([], ctx.hass_api, discover=True)
    uut.initialize()

    assert len(uut.filter_people_by_occupancy("all_in")) == 0
    assert len(uut.filter_people_by_occupancy("all_out")) == 0
    assert len(uut.filter_people_by_occupancy("any_in")) == 2
    assert len(uut.filter_people_by_occupancy("any_out")) == 2
    assert len(uut.filter_people_by_occupancy("only_in")) == 1
    assert len(uut.filter_people_by_occupancy("only_out")) == 1

    assert {r.entity_id for r in uut.filter_people_by_occupancy("only_out")} == {"person.mae_mctest"}
    assert {r.entity_id for r in uut.filter_people_by_occupancy("only_in")} == {"person.joe_mctest"}
