"""Tests for area_id / floor_id / label_id target selectors (issue #9).

Selectors are always resolved to the entities they reference, within the target code, through
the same core helper as a Home Assistant entity action, so transports never see a selector.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.const import ATTR_AREA_ID, ATTR_ENTITY_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID, CONF_ACTION, CONF_TARGET
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import label_registry as lr

from custom_components.supernotify.const import (
    CONF_DELIVERY,
    CONF_TARGET_REQUIRED,
    CONF_TRANSPORT,
    TRANSPORT_GENERIC,
    TRANSPORT_NOTIFY_ENTITY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import HomeAssistantAPI, TargetSelectorResolution
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# ---------------------------------------------------------------------------
# Target model
# ---------------------------------------------------------------------------


def _resolver(mapping: dict[str, list[str]], missing: tuple[str, ...] = ()) -> object:
    """Stand in for HomeAssistantAPI.resolve_target_selectors, one selector value at a time"""

    def resolve(
        area_ids: list[str] | None = None, floor_ids: list[str] | None = None, label_ids: list[str] | None = None
    ) -> TargetSelectorResolution:
        values: list[str] = (area_ids or []) + (floor_ids or []) + (label_ids or [])
        resolution = TargetSelectorResolution(entity_ids=[e for v in values for e in mapping.get(v, [])])
        if area_ids and area_ids[0] in missing:
            resolution.missing_areas = list(area_ids)
        if floor_ids and floor_ids[0] in missing:
            resolution.missing_floors = list(floor_ids)
        if label_ids and label_ids[0] in missing:
            resolution.missing_labels = list(label_ids)
        return resolution

    return resolve


def _hass_api(mapping: dict[str, list[str]], missing: tuple[str, ...] = ()) -> HomeAssistantAPI:
    hass_api = object.__new__(HomeAssistantAPI)
    hass_api.resolve_target_selectors = _resolver(mapping, missing)  # type: ignore[method-assign, assignment] # ty:ignore[invalid-assignment]
    return hass_api


def test_target_without_selectors_resolves_to_itself() -> None:
    uut = Target({ATTR_ENTITY_ID: ["light.a"]})
    assert uut.resolve_selectors(_hass_api({})) is uut


def test_target_resolves_selectors_to_entities_once() -> None:
    hass_api = _hass_api({
        "kitchen": ["light.kitchen", "switch.chime"],
        "ground": ["light.kitchen", "media_player.lounge"],
        "voice": ["media_player.lounge"],
    })
    uut = Target({
        ATTR_ENTITY_ID: ["switch.chime"],
        ATTR_AREA_ID: ["kitchen"],
        ATTR_FLOOR_ID: ["ground"],
        ATTR_LABEL_ID: ["voice"],
    })
    resolved = uut.resolve_selectors(hass_api)
    # an entity in the kitchen, on the first floor and labelled voice is kept just once
    assert resolved.entity_ids == ["switch.chime", "light.kitchen", "media_player.lounge"]
    assert resolved.area_ids == []
    assert resolved.floor_ids == []
    assert resolved.label_ids == []
    # the original is left untouched
    assert uut.area_ids == ["kitchen"]


def test_target_keeps_other_categories_and_data_when_resolving() -> None:
    uut = Target({ATTR_AREA_ID: ["kitchen"], "person_id": ["person.bob"], "email": ["bob@test.org"]})
    uut.target_data = {"volume": 0.5}
    resolved = uut.resolve_selectors(_hass_api({"kitchen": ["light.kitchen"]}))
    assert resolved.entity_ids == ["light.kitchen"]
    assert resolved.person_ids == ["person.bob"]
    assert resolved.targets["email"] == ["bob@test.org"]
    assert resolved.target_data == {"volume": 0.5}


def test_target_selector_data_inherited_by_its_entities() -> None:
    uut = Target({ATTR_AREA_ID: ["kitchen"], ATTR_ENTITY_ID: ["light.kitchen"]})
    uut.target_specific_data = {
        (ATTR_AREA_ID, "kitchen"): {"volume": 0.2},
        (ATTR_ENTITY_ID, "light.kitchen"): {"volume": 0.9},
    }
    resolved = uut.resolve_selectors(_hass_api({"kitchen": ["light.kitchen", "switch.chime"]}))
    # data attached to the entity itself wins over data inherited from the area
    assert resolved.target_specific_data == {
        (ATTR_ENTITY_ID, "light.kitchen"): {"volume": 0.9},
        (ATTR_ENTITY_ID, "switch.chime"): {"volume": 0.2},
    }


def test_target_warns_on_unknown_selectors(caplog: pytest.LogCaptureFixture) -> None:
    uut = Target({ATTR_AREA_ID: ["kitchn"], ATTR_LABEL_ID: ["chime"]})
    resolved = uut.resolve_selectors(_hass_api({}, missing=("kitchn", "chime")))
    assert resolved.entity_ids == []
    assert "Unknown target selectors area_id:kitchn, label_id:chime" in caplog.text


async def test_delivery_selection_resolves_selectors_before_filtering() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    target = Target({ATTR_ENTITY_ID: ["notify.pong"], ATTR_AREA_ID: ["kitchen"], ATTR_LABEL_ID: ["chimes"]})
    with patch.object(
        ctx.hass_api, "resolve_target_selectors", side_effect=_resolver({"kitchen": ["notify.hob", "light.nope"]})
    ):
        # the entities of the area go through the same category filter as any other entity, so
        # the light is dropped and the notify entity kept
        assert uut.select_targets(target) == Target(["notify.pong", "notify.hob"])


# ---------------------------------------------------------------------------
# Home Assistant API: resolution against the real registries
# ---------------------------------------------------------------------------


def test_resolve_target_selectors_empty(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    resolution = uut.resolve_target_selectors()
    assert resolution.entity_ids == []
    assert not resolution.has_missing()


def _register_entity(hass: HomeAssistant, domain: str, uid: str, area_id: str | None = None) -> str:
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(domain, "unit_test", uid, suggested_object_id=uid)
    if area_id:
        entry = registry.async_update_entity(entry.entity_id, area_id=area_id)
    hass.states.async_set(entry.entity_id, "on")
    return entry.entity_id


def test_resolve_target_selectors_by_area_floor_label(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    floor = fr.async_get(hass).async_create("Ground")
    kitchen = ar.async_get(hass).async_create("Kitchen", floor_id=floor.floor_id)
    lounge = ar.async_get(hass).async_create("Lounge", floor_id=floor.floor_id)
    attic = ar.async_get(hass).async_create("Attic")
    label = lr.async_get(hass).async_create("Chimes")

    kitchen_chime = _register_entity(hass, "switch", "kitchen_chime", area_id=kitchen.id)
    kitchen_light = _register_entity(hass, "light", "kitchen_light", area_id=kitchen.id)
    lounge_speaker = _register_entity(hass, "media_player", "lounge_speaker", area_id=lounge.id)
    attic_chime = _register_entity(hass, "switch", "attic_chime", area_id=attic.id)
    er.async_get(hass).async_update_entity(attic_chime, labels={label.label_id})
    er.async_get(hass).async_update_entity(kitchen_chime, labels={label.label_id})

    by_area = uut.resolve_target_selectors(area_ids=[kitchen.id])
    assert by_area.entity_ids == sorted([kitchen_chime, kitchen_light])
    assert not by_area.has_missing()

    by_floor = uut.resolve_target_selectors(floor_ids=[floor.floor_id])
    assert by_floor.entity_ids == sorted([kitchen_chime, kitchen_light, lounge_speaker])

    by_label = uut.resolve_target_selectors(label_ids=[label.label_id])
    assert by_label.entity_ids == sorted([attic_chime, kitchen_chime])

    # overlapping selectors dedupe to a single entity set
    combined = uut.resolve_target_selectors(area_ids=[kitchen.id], floor_ids=[floor.floor_id], label_ids=[label.label_id])
    assert combined.entity_ids == sorted([attic_chime, kitchen_chime, kitchen_light, lounge_speaker])


def test_resolve_target_selectors_reports_missing(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    resolution = uut.resolve_target_selectors(area_ids=["nowhere"], floor_ids=["basement"], label_ids=["nope"])
    assert resolution.entity_ids == []
    assert resolution.has_missing()
    assert resolution.missing_areas == ["nowhere"]
    assert resolution.missing_floors == ["basement"]
    assert resolution.missing_labels == ["nope"]


def test_resolve_target_selectors_survives_errors(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    uut = HomeAssistantAPI(hass)
    with patch("custom_components.supernotify.hass_api.async_extract_referenced_entity_ids", side_effect=RuntimeError("boom")):
        resolution = uut.resolve_target_selectors(area_ids=["kitchen"])
    assert resolution.entity_ids == []
    assert "Unable to resolve target selectors" in caplog.text


# ---------------------------------------------------------------------------
# Notification: target generation end to end
# ---------------------------------------------------------------------------


async def _generic_context(target_required: str | None = None) -> TestingContext:
    conf: dict[str, str] = {CONF_ACTION: "custom.tweak", CONF_TRANSPORT: TRANSPORT_GENERIC}
    if target_required:
        conf[CONF_TARGET_REQUIRED] = target_required
    ctx = TestingContext(deliveries={"chatty": conf})
    await ctx.test_initialize()
    return ctx


async def test_generate_targets_resolves_area_to_entities() -> None:
    ctx = await _generic_context()
    delivery = ctx.delivery("chatty")
    with patch.object(
        ctx.hass_api, "resolve_target_selectors", side_effect=_resolver({"kitchen": ["custom.light_1", "custom.switch_2"]})
    ):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchen"], ATTR_ENTITY_ID: ["custom.switch_2"]})
        targets: list[Target] = uut.generate_targets(delivery)
    assert len(targets) == 1
    # deduped against the explicit entity target, and the selector itself gone
    assert targets[0].entity_ids == ["custom.switch_2", "custom.light_1"]
    assert targets[0].area_ids == []


async def test_generate_targets_warns_on_unknown_selectors(caplog: pytest.LogCaptureFixture) -> None:
    ctx = await _generic_context()
    delivery = ctx.delivery("chatty")
    with patch.object(ctx.hass_api, "resolve_target_selectors", side_effect=_resolver({}, missing=("kitchn", "chime"))):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchn"], ATTR_LABEL_ID: ["chime"]})
        targets: list[Target] = uut.generate_targets(delivery)
    assert targets[0].entity_ids == []
    assert targets[0].area_ids == []
    assert "Unknown target selectors area_id:kitchn, label_id:chime" in caplog.text


async def test_no_envelope_when_selectors_resolve_to_nothing_and_target_required() -> None:
    ctx = await _generic_context(target_required="always")
    delivery = ctx.delivery("chatty")
    with patch.object(ctx.hass_api, "resolve_target_selectors", side_effect=_resolver({})):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchen"]})
        envelopes = uut.generate_envelopes(delivery, uut.generate_targets(delivery))
    assert envelopes == []


async def test_delivery_override_target_resolves_selectors() -> None:
    ctx = await _generic_context()
    delivery = ctx.delivery("chatty")
    with patch.object(ctx.hass_api, "resolve_target_selectors", side_effect=_resolver({"lights": ["custom.light_1"]})):
        uut = Notification(
            ctx,
            "testing 123",
            target=["custom.switch_9"],
            action_data={CONF_DELIVERY: {"chatty": {CONF_TARGET: {ATTR_LABEL_ID: ["lights"]}}}},
        )
        targets: list[Target] = uut.generate_targets(delivery)
    assert targets[0].entity_ids == ["custom.light_1"]
    assert targets[0].label_ids == []


async def test_transport_never_sees_selectors(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config
    uut = NotifyEntityTransport(context)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    delivery = Delivery("ping", {CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY}, uut)
    await delivery.initialize(context)
    with patch.object(context.hass_api, "resolve_target_selectors", side_effect=_resolver({"kitchen": ["notify.hob"]})):
        selected = delivery.select_targets(Target({ATTR_ENTITY_ID: ["notify.pong"], ATTR_AREA_ID: ["kitchen"]}))
    assert selected == Target(["notify.pong", "notify.hob"])
    assert selected.area_ids == []
