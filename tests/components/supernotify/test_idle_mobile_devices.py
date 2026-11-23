"""Mobile devices nobody is using - a sleeping Mac, a watch not worn - left out of a notification,
from the Companion app's own in-use sensor, found in the entity registry"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigSubentryData
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import (
    CONF_IN_USE_ENTITY,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_PERSON,
    CONF_SEND_WHEN_IDLE,
    SUBENTRY_TYPE_RECIPIENT,
)
from custom_components.supernotify.hass_api import HomeAssistantAPI, companion_sensor_id
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import Recipient
from custom_components.supernotify.schema import MOBILE_DEVICE_SCHEMA
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from tests.components.supernotify.ha_testing import MockConfigEntry

from .hass_setup_lib import TestingContext, first_envelope, register_mobile_app, set_state

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PHONE = "mobile_app_bob_phone"
LAPTOP = "mobile_app_bob_laptop"
WATCH = "mobile_app_bob_watch"
LAPTOP_SENSOR = "binary_sensor.bob_laptop_active"
WATCH_SENSOR = "binary_sensor.bob_watch_on_body"


def test_companion_sensor_id() -> None:
    assert companion_sensor_id("0123abcd_active") == "active"
    assert companion_sensor_id("0123abcd_on_body") == "on_body"
    assert companion_sensor_id("0123abcd_is_interactive") == "is_interactive"
    assert companion_sensor_id("no-sensor-id") is None
    assert companion_sensor_id(None) is None


def test_schema_takes_in_use_entity_and_send_when_idle() -> None:
    device = MOBILE_DEVICE_SCHEMA({CONF_MOBILE_APP_ID: LAPTOP, CONF_IN_USE_ENTITY: LAPTOP_SENSOR, CONF_SEND_WHEN_IDLE: "yes"})
    assert device[CONF_IN_USE_ENTITY] == LAPTOP_SENSOR
    assert device[CONF_SEND_WHEN_IDLE] is True


async def _ctx(**laptop: Any) -> TestingContext:
    ctx = TestingContext(
        recipients=[
            {
                CONF_PERSON: "person.bob_mctest",
                CONF_MOBILE_DEVICES: [
                    {CONF_MOBILE_APP_ID: PHONE},
                    {CONF_MOBILE_APP_ID: LAPTOP, CONF_IN_USE_ENTITY: LAPTOP_SENSOR, **laptop},
                    {CONF_MOBILE_APP_ID: WATCH, CONF_IN_USE_ENTITY: WATCH_SENSOR},
                ],
            },
        ],
        services={"notify": [PHONE, LAPTOP, WATCH]},
    )
    await ctx.test_initialize()
    return ctx


async def _send(ctx: TestingContext, message: str = "Hello", **kwargs: Any) -> Notification:
    uut = Notification(ctx, message=message, **kwargs)
    await uut.initialize()
    await uut.deliver()
    return uut


async def test_idle_devices_left_out() -> None:
    ctx = await _ctx()
    set_state(ctx.hass_api, LAPTOP_SENSOR, STATE_OFF)
    set_state(ctx.hass_api, WATCH_SENSOR, STATE_ON)

    uut = await _send(ctx, action_data={"debug": True})
    envelope = first_envelope(uut, "mobile_push")
    assert envelope.target.mobile_app_ids == [PHONE, WATCH]
    # the person stays in the target
    assert envelope.target.person_ids == ["person.bob_mctest"]
    # and the trace says which device was left out, and by which sensor
    assert uut.debug_trace.delivery_artefacts["mobile_push"]["idle_mobile_devices"] == {LAPTOP: LAPTOP_SENSOR}


@pytest.mark.parametrize("state", [STATE_ON, STATE_UNKNOWN, STATE_UNAVAILABLE, None])
async def test_devices_not_plainly_idle_are_notified(state: str | None) -> None:
    ctx = await _ctx()
    if state is not None:
        set_state(ctx.hass_api, LAPTOP_SENSOR, state)
        set_state(ctx.hass_api, WATCH_SENSOR, state)

    envelope = first_envelope(await _send(ctx), "mobile_push")
    assert envelope.target.mobile_app_ids == [PHONE, LAPTOP, WATCH]


async def test_send_when_idle() -> None:
    ctx = await _ctx(**{CONF_SEND_WHEN_IDLE: True})
    set_state(ctx.hass_api, LAPTOP_SENSOR, STATE_OFF)
    set_state(ctx.hass_api, WATCH_SENSOR, STATE_OFF)

    envelope = first_envelope(await _send(ctx), "mobile_push")
    assert envelope.target.mobile_app_ids == [PHONE, LAPTOP]


@pytest.mark.parametrize("action_data", [{"priority": "critical"}, {"include_idle_devices": True}])
async def test_critical_or_asked_for_reaches_idle_devices(action_data: dict[str, Any]) -> None:
    ctx = await _ctx()
    set_state(ctx.hass_api, LAPTOP_SENSOR, STATE_OFF)
    set_state(ctx.hass_api, WATCH_SENSOR, STATE_OFF)

    envelope = first_envelope(await _send(ctx, action_data=action_data), "mobile_push")
    assert envelope.target.mobile_app_ids == [PHONE, LAPTOP, WATCH]


async def test_device_given_in_the_action_is_notified_even_when_idle() -> None:
    ctx = await _ctx()
    set_state(ctx.hass_api, LAPTOP_SENSOR, STATE_OFF)

    envelope = first_envelope(await _send(ctx, target=[LAPTOP]), "mobile_push")
    assert envelope.target.mobile_app_ids == [LAPTOP]


def test_all_idle_means_none_left_out(hass: HomeAssistant) -> None:
    """So the notification still reaches the person somewhere"""
    hass_api = HomeAssistantAPI(hass)
    set_state(hass_api, LAPTOP_SENSOR, STATE_OFF)
    set_state(hass_api, WATCH_SENSOR, STATE_OFF)
    bob = Recipient({
        CONF_PERSON: "person.bob_mctest",
        CONF_MOBILE_DEVICES: [
            {CONF_MOBILE_APP_ID: LAPTOP, CONF_IN_USE_ENTITY: LAPTOP_SENSOR},
            {CONF_MOBILE_APP_ID: WATCH, CONF_IN_USE_ENTITY: WATCH_SENSOR},
        ],
    })
    assert bob.idle_mobile_app_ids([LAPTOP, WATCH], hass_api) == {}
    assert bob.idle_mobile_app_ids([f"notify.{LAPTOP}", PHONE], hass_api) == {f"notify.{LAPTOP}": LAPTOP_SENSOR}
    # a device the recipient doesn't have isn't theirs to judge
    assert bob.idle_mobile_app_ids(["mobile_app_someone_else"], hass_api) == {}


def _add_sensor(hass_api: HomeAssistantAPI, device_name: str, sensor_id: str, **kwargs: Any) -> str:
    hass = hass_api._hass
    slug = device_name.lower().replace(" ", "_")
    device = next(d for d in hass_api.mobile_app_by_user_id(_user_id(hass)) or [] if d.mobile_app_id == f"mobile_app_{slug}")
    entry = er.async_get(hass).async_get_or_create(
        "binary_sensor",
        "mobile_app",
        # as mobile_app has it, prefixed by the device's own webhook id, which is hex
        f"{hashlib.md5(slug.encode()).hexdigest()}_{sensor_id}",
        suggested_object_id=f"{slug}_{sensor_id}",
        device_id=device.device_id,
        **kwargs,
    )
    hass_api.build_mobile_app_cache()
    return entry.entity_id


async def test_in_use_sensor_discovered(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.test_user"}],
        components={"person": {}},
        transport_types=[MobilePushTransport],
    )
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Laptop", os_name="macOS")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Watch", os_name="Android")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Phone", os_name="Android")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Tablet", os_name="Android")
    laptop_sensor = _add_sensor(ctx.hass_api, "Bobs Laptop", "active")
    watch_sensor = _add_sensor(ctx.hass_api, "Bobs Watch", "on_body")
    # screen off is no sign a phone isn't in use, so `is_interactive` isn't taken
    _add_sensor(ctx.hass_api, "Bobs Phone", "is_interactive")
    # nor is a sensor switched off in Home Assistant, as it has no state
    _add_sensor(ctx.hass_api, "Bobs Tablet", "active", disabled_by=er.RegistryEntryDisabler.USER)

    devices = {d.mobile_app_id: d for d in ctx.hass_api.mobile_app_by_user_id(_user_id(hass)) or []}
    assert devices["mobile_app_bobs_laptop"].in_use_entity == laptop_sensor
    assert devices["mobile_app_bobs_watch"].in_use_entity == watch_sensor
    assert devices["mobile_app_bobs_phone"].in_use_entity is None
    assert devices["mobile_app_bobs_tablet"].in_use_entity is None

    await ctx.test_initialize()
    set_state(ctx.hass_api, laptop_sensor, STATE_OFF)
    set_state(ctx.hass_api, watch_sensor, STATE_ON)
    bob: Recipient = ctx.people_registry.people["person.test_user"]
    assert bob.idle_mobile_app_ids(list(bob.enabled_mobile_devices), ctx.hass_api) == {"mobile_app_bobs_laptop": laptop_sensor}


async def test_configured_in_use_entity_wins_over_discovered(hass: HomeAssistant) -> None:
    """As for an Android tablet, whose `is_interactive` isn't taken by default"""
    ctx = TestingContext(
        homeassistant=hass,
        recipients="""
    - person: person.test_user
      mobile_devices:
        - mobile_app_id: mobile_app_bobs_tablet
          in_use_entity: binary_sensor.bobs_tablet_is_interactive
""",
        components={"person": {}},
        transport_types=[MobilePushTransport],
    )
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Phone")
    register_mobile_app(ctx.hass_api, person="person.test_user", device_name="Bobs Tablet")
    _add_sensor(ctx.hass_api, "Bobs Tablet", "active")
    await ctx.test_initialize()

    bob: Recipient = ctx.people_registry.people["person.test_user"]
    assert bob.mobile_devices["mobile_app_bobs_tablet"][CONF_IN_USE_ENTITY] == "binary_sensor.bobs_tablet_is_interactive"
    set_state(ctx.hass_api, "binary_sensor.bobs_tablet_is_interactive", STATE_OFF)
    assert bob.idle_mobile_app_ids(list(bob.enabled_mobile_devices), ctx.hass_api) == {
        "mobile_app_bobs_tablet": "binary_sensor.bobs_tablet_is_interactive"
    }


def _user_id(hass: HomeAssistant) -> str:
    state = hass.states.get("person.test_user")
    assert state is not None
    return str(state.attributes["user_id"])


async def test_recipient_form_keeps_device_settings_and_sets_send_when_idle(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    register_mobile_app(hass_api, person="person.bob", device_name="Bob Phone")
    register_mobile_app(hass_api, person="person.bob", device_name="Bob Laptop")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"recipients_discovery": False},
        options={},
        subentries_data=[
            ConfigSubentryData(
                data={
                    "person": "person.bob",
                    "mobile_devices": [
                        {"mobile_app_id": LAPTOP, "enabled": True, "in_use_entity": LAPTOP_SENSOR, "send_when_idle": True}
                    ],
                },
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title="person.bob",
                unique_id="person.bob",
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"delivery": {"testing": {"transport": "generic", "action": "notify.send_message"}}}}
    )
    await hass.async_block_till_done()
    (subentry,) = [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TYPE_RECIPIENT]

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_RECIPIENT), context={"source": SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id}
    )
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested["send_when_idle"] == [LAPTOP]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"enabled": True, "mobile_discovery": True, "mobile_devices": [PHONE, LAPTOP], "send_when_idle": [PHONE]},
    )
    assert result["type"] == FlowResultType.ABORT
    await hass.async_block_till_done()
    assert {d["mobile_app_id"]: d for d in subentry.data["mobile_devices"]} == {
        PHONE: {"mobile_app_id": PHONE, "enabled": True, "send_when_idle": True},
        # set only in YAML, and kept
        LAPTOP: {"mobile_app_id": LAPTOP, "enabled": True, "in_use_entity": LAPTOP_SENSOR},
    }
