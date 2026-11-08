"""Tests for the LG webOS TV transport"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er

from custom_components.supernotify.model import TransportFeature
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from custom_components.supernotify.transports.webostv import WebOsTvTransport
from tests.components.supernotify.ha_testing import MockConfigEntry
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


def add_tv(hass: HomeAssistant, title: str, object_id: str, state: str = "on") -> str:
    """A TV as the webostv integration sets one up - a config entry, its media_player and its notify action"""
    entry = MockConfigEntry(domain="webostv", title=title, data={})
    entry.add_to_hass(hass)
    reg_entry = er.async_get(hass).async_get_or_create(
        "media_player", "webostv", f"{object_id}_id", suggested_object_id=object_id, config_entry=entry
    )
    hass.states.async_set(reg_entry.entity_id, state)
    return reg_entry.entity_id


async def setup(hass: HomeAssistant, *tvs: tuple[str, str, str]) -> tuple[TestingContext, list[ServiceCall], list[str]]:
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    entity_ids: list[str] = []
    for title, object_id, state in tvs:
        entity_ids.append(add_tv(hass, title, object_id, state))
        hass.services.async_register("notify", object_id, record)
    ctx = TestingContext(homeassistant=hass, transport_types=[WebOsTvTransport])
    await ctx.test_initialize()
    return ctx, calls, entity_ids


async def test_standard_delivery_only_when_integration_set_up(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, transport_types=[WebOsTvTransport])
    await ctx.test_initialize()
    assert "webostv" not in ctx.delivery_registry.deliveries

    ctx, _, _ = await setup(hass, ("Living Room TV", "living_room_tv", "on"))
    assert "webostv" in ctx.delivery_registry.deliveries
    assert "webostv" in [d.name for d in ctx.delivery_registry.implicit_deliveries]
    assert ctx.delivery_registry.deliveries["webostv"].transport.supported_features == TransportFeature.MESSAGE


async def test_sends_to_each_tv_by_its_own_action(hass: HomeAssistant) -> None:
    ctx, calls, (lounge, bedroom) = await setup(hass, ("Lounge TV", "lounge_tv", "on"), ("Bedroom TV", "bedroom_tv", "on"))

    uut = Notification(ctx, "Dinner is ready", target=[lounge, bedroom])
    await uut.initialize()
    await uut.deliver()

    assert list(uut.selected_deliveries) == ["webostv"]
    assert sorted(c.service for c in calls) == ["bedroom_tv", "lounge_tv"]
    assert all(c.data == {"message": "Dinner is ready"} for c in calls)


async def test_not_selected_without_a_tv_target(hass: HomeAssistant) -> None:
    ctx, calls, _ = await setup(hass, ("Lounge TV", "lounge_tv", "on"))

    uut = Notification(ctx, "Dinner is ready")
    await uut.initialize()
    await uut.deliver()

    assert "webostv" not in uut.selected_deliveries
    assert calls == []


async def test_skips_tvs_that_are_off_or_unavailable(hass: HomeAssistant) -> None:
    ctx, calls, entity_ids = await setup(
        hass,
        ("Lounge TV", "lounge_tv", "on"),
        ("Bedroom TV", "bedroom_tv", "off"),
        ("Garage TV", "garage_tv", "unavailable"),
    )

    uut = Notification(ctx, "Dinner is ready", target=entity_ids)
    await uut.initialize()
    await uut.deliver()

    assert [c.service for c in calls] == ["lounge_tv"]


async def test_all_tvs_off_is_skipped_not_an_error(hass: HomeAssistant) -> None:
    ctx, calls, (bedroom,) = await setup(hass, ("Bedroom TV", "bedroom_tv", "off"))

    uut = Notification(ctx, "Dinner is ready", target=[bedroom])
    await uut.initialize()
    await uut.deliver()

    assert calls == []
    assert uut.deliveries["webostv"].get(EnvelopeOutcome.SUPPRESSED)
    assert not uut.deliveries["webostv"].get(EnvelopeOutcome.ERROR)
    assert uut.error_count == 0


async def test_title_only_used_without_message(hass: HomeAssistant) -> None:
    ctx, calls, (lounge,) = await setup(hass, ("Lounge TV", "lounge_tv", "on"))

    uut = Notification(ctx, "Dinner is ready", title="Kitchen", target=[lounge])
    await uut.initialize()
    await uut.deliver()
    uut = Notification(ctx, None, title="Kitchen", target=[lounge])
    await uut.initialize()
    await uut.deliver()

    assert [c.data["message"] for c in calls] == ["Dinner is ready", "Kitchen"]


async def test_icon_passed_through_other_data_dropped(hass: HomeAssistant) -> None:
    ctx, calls, (lounge,) = await setup(hass, ("Lounge TV", "lounge_tv", "on"))

    uut = Notification(
        ctx, "Dinner is ready", target=[lounge], action_data={"data": {"icon": "/config/www/dinner.png", "other": 1}}
    )
    await uut.initialize()
    await uut.deliver()

    assert calls[0].data == {"message": "Dinner is ready", "data": {"icon": "/config/www/dinner.png"}}


async def test_tv_without_notify_action_is_missed(hass: HomeAssistant) -> None:
    entity_id = add_tv(hass, "Lounge TV", "lounge_tv")
    ctx = TestingContext(homeassistant=hass, transport_types=[WebOsTvTransport])
    await ctx.test_initialize()

    uut = Notification(ctx, "Dinner is ready", target=[entity_id])
    await uut.initialize()
    await uut.deliver()

    assert uut.deliveries["webostv"].get(EnvelopeOutcome.SUPPRESSED)
