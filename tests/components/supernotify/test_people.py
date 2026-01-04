from homeassistant.components import person
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from pytest_unordered import unordered

from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import PeopleRegistry, Recipient
from custom_components.supernotify.transports.mobile_push import MobilePushTransport

from .hass_setup_lib import TestingContext, register_mobile_app


async def test_people_registry_finds_people(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, components={"person": {}})
    await ctx.test_initialize()
    await person.async_create_person(hass, "Joe McTest")
    await person.async_create_person(hass, "Mae McTest")

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
    device = register_mobile_app(hass_api, person="person.test_user", device_name="Bobs Phone")
    assert device is not None
    mobiles = uut.mobile_devices_for_person("person.test_user")
    assert len(mobiles) == 1
    mobile = mobiles[0]

    assert mobile.manufacturer == "xUnit"
    assert mobile.model == "PyTest001"
    assert mobile.action == "notify.mobile_app_bobs_phone"
    assert mobile.mobile_app_id == "mobile_app_bobs_phone"
    assert mobile.device_tracker == "device_tracker.mobile_app_bobs_phone"
    assert mobile.device_id == device.id
    assert mobile.device_name == "Bobs Phone"


async def test_autoresolve_mobile_devices_blended_with_manual_registration(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        recipients="""
    - person: person.test_user
      mobile_devices:
        - mobile_app_id: mobile_app_old_laptop
        - mobile_app_id: mobile_app_ipad11
        - mobile_app_id: mobile_app_bobs_watch
        - mobile_app_id: mobile_app_bobs_broken_phone
          enabled: False
""",
        components={"person": {}},
        transport_types=[MobilePushTransport],
    )
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Phone")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Watch")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Broken Phone")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Other Phone")
    await ctx.test_initialize()

    bob: Recipient = ctx.people_registry.people["person.test_user"]
    assert list(bob.enabled_mobile_devices) == unordered(
        "mobile_app_old_laptop",
        "mobile_app_ipad11",
        "mobile_app_bobs_watch",
        "mobile_app_bobs_phone",
        "mobile_app_bobs_other_phone",
    )

    n: Notification = Notification(ctx, "testing 123")
    await n.initialize()
    await n.deliver()
    assert n.delivered_envelopes[0].target.mobile_app_ids == unordered(
        "mobile_app_old_laptop",
        "mobile_app_ipad11",
        "mobile_app_bobs_watch",
        "mobile_app_bobs_phone",
        "mobile_app_bobs_other_phone",
    )


async def test_filter_recipients(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, components={"person": {}})
    await ctx.test_initialize()
    await person.async_create_person(hass, "Joe McTest")
    await person.async_create_person(hass, "Mae McTest")
    await hass.async_block_till_done()
    hass.states.async_set("person.joe_mctest", "home")
    hass.states.async_set("person.mae_mctest", "not_home")
    uut = PeopleRegistry([], ctx.hass_api, discover=True)
    uut.initialize()

    assert len(uut.filter_recipients_by_occupancy("all_in")) == 0
    assert len(uut.filter_recipients_by_occupancy("all_out")) == 0
    assert len(uut.filter_recipients_by_occupancy("any_in")) == 2
    assert len(uut.filter_recipients_by_occupancy("any_out")) == 2
    assert len(uut.filter_recipients_by_occupancy("only_in")) == 1
    assert len(uut.filter_recipients_by_occupancy("only_out")) == 1

    assert {r.entity_id for r in uut.filter_recipients_by_occupancy("only_out")} == {"person.mae_mctest"}
    assert {r.entity_id for r in uut.filter_recipients_by_occupancy("only_in")} == {"person.joe_mctest"}
