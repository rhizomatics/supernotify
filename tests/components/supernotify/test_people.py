from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import homeassistant.util.dt as dt_util
from homeassistant.components import person
from homeassistant.core import State
from pytest_unordered import unordered

from custom_components.supernotify.const import CONF_PERSON
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import PeopleRegistry, Recipient, RecipientNotifyEntity
from custom_components.supernotify.transports.mobile_push import MobilePushTransport

from .hass_setup_lib import TestingContext, register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry, entity_registry


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
    assert mobile.device_tracker == "device_tracker.bobs_phone"
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


def test_recipient_notify_entity_record_notification(hass: HomeAssistant) -> None:
    """record_notification() is how Notification.record_result() reflects a delivery that went
    through supernotify.notify's main pipeline rather than a direct notify.recipient_alice call.
    On HA >= 2026.3 (where NotifyEntity._async_record_notification() exists) this uses the
    entity's own native `state`; on HA < 2026.3 it falls back to a separate last_notified
    attribute - see the docstring on RecipientNotifyEntity.record_notification() for why both
    paths exist. This test runs unmodified on both lanes and checks whichever mechanism this HA
    version actually provides."""
    recipient = Recipient({CONF_PERSON: "person.alice"})
    uut = RecipientNotifyEntity("entry123_recipient_alice", recipient, Mock())
    uut.hass = hass
    native = hasattr(uut, "_async_record_notification")

    if native:
        assert uut.state is None
    else:
        assert uut.extra_state_attributes == {"last_notified": None}

    before = dt_util.utcnow()
    uut.record_notification()
    after = dt_util.utcnow()

    if native:
        assert uut.state is not None
        recorded = dt_util.parse_datetime(uut.state)
        assert recorded is not None
        assert before <= recorded <= after
        assert hass.states.get("notify.recipient_alice").state == uut.state
    else:
        assert uut.extra_state_attributes is not None
        last_notified = uut.extra_state_attributes["last_notified"]
        recorded = dt_util.parse_datetime(last_notified)
        assert recorded is not None
        assert before <= recorded <= after
        assert hass.states.get("notify.recipient_alice").attributes["last_notified"] == last_notified


async def test_recipient_notify_entity_links_itself_to_recipient_on_added_to_hass(hass: HomeAssistant) -> None:
    """The Recipient needs a live reference to its RecipientNotifyEntity (not just the
    entity_id) so Notification._record_recipient_notifications() can call record_notification()
    directly without a registry lookup - set/cleared alongside the pre-existing notify_entity_id
    tracking."""
    recipient = Recipient({CONF_PERSON: "person.alice"})
    uut = RecipientNotifyEntity("entry123_recipient_alice", recipient, Mock())
    uut.hass = hass
    uut.async_get_last_state = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await uut.async_added_to_hass()

    assert recipient.notify_entity is uut
    assert recipient.notify_entity_id == "notify.recipient_alice"

    await uut.async_will_remove_from_hass()

    assert recipient.notify_entity is None
    assert recipient.notify_entity_id is None


async def test_recipient_notify_entity_restores_last_notified_on_added_to_hass(hass: HomeAssistant) -> None:
    """The recorded notification timestamp survives a restart via HA's own restore-state
    mechanism (NotifyEntity is already a RestoreEntity), same as the notification/failure
    counters restore themselves via SupernotifyCounterSensor. On HA >= 2026.3 this restore is
    native (NotifyEntity.async_internal_added_to_hass(), reading state.state); on HA < 2026.3 -
    where there's no such native mechanism - RecipientNotifyEntity.async_added_to_hass() does it
    manually from the last_notified attribute, same as before the refactor. This test runs
    unmodified on both lanes."""
    recipient = Recipient({CONF_PERSON: "person.alice"})
    uut = RecipientNotifyEntity("entry123_recipient_alice", recipient, Mock())
    uut.hass = hass
    native = hasattr(uut, "_async_record_notification")

    if native:
        restored_state = State("notify.recipient_alice", "2026-09-07T09:00:00+00:00")
        uut.async_get_last_state = AsyncMock(return_value=restored_state)  # type: ignore[method-assign]
        # async_internal_added_to_hass() (unlike async_added_to_hass()) is normally only called
        # by the entity platform machinery, which sets self.platform first - stub the bit of it
        # this method actually touches.
        uut.platform = Mock(platform_name="notify", config_entry=None)
        await uut.async_internal_added_to_hass()
        assert uut.state == "2026-09-07T09:00:00+00:00"
    else:
        restored_state = State(
            "notify.recipient_alice", "2026-09-07T09:00:00+00:00", {"last_notified": "2026-09-07T09:00:00+00:00"}
        )
        uut.async_get_last_state = AsyncMock(return_value=restored_state)  # type: ignore[method-assign]
        await uut.async_added_to_hass()
        assert uut.extra_state_attributes == {"last_notified": "2026-09-07T09:00:00+00:00"}
