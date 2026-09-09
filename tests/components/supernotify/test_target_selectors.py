"""Tests for area_id / floor_id / label_id target selectors (issue #9).

Selectors are either passed through untouched to actions that accept them natively (discovered
from the action description, or forced with the `target_selectors` delivery option), or resolved
to entity_ids within supernotify using the same core helper as HA entity actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.const import ATTR_AREA_ID, ATTR_ENTITY_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID, CONF_ACTION, CONF_TARGET
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers import label_registry as lr

from custom_components.supernotify.const import (
    CONF_DELIVERY,
    CONF_OPTIONS,
    CONF_TARGET_REQUIRED,
    CONF_TRANSPORT,
    OPTION_TARGET_SELECTORS,
    TARGET_SELECTORS_NATIVE,
    TARGET_SELECTORS_RESOLVE,
    TRANSPORT_CHIME,
    TRANSPORT_GENERIC,
    TRANSPORT_NOTIFY_ENTITY,
    TRANSPORT_TTS,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import HomeAssistantAPI, TargetSelectorResolution
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.context import Context

# ---------------------------------------------------------------------------
# Target model
# ---------------------------------------------------------------------------


def test_target_selector_helpers() -> None:
    uut = Target({ATTR_ENTITY_ID: ["light.a"], ATTR_AREA_ID: ["kitchen"], ATTR_FLOOR_ID: [], ATTR_LABEL_ID: ["chimes"]})
    assert uut.has_selectors()
    assert uut.selector_data() == {ATTR_AREA_ID: ["kitchen"], ATTR_LABEL_ID: ["chimes"]}
    assert not Target(["light.a"]).has_selectors()
    assert Target(["light.a"]).selector_data() == {}


def test_target_direct_drops_selectors_by_default() -> None:
    uut = Target({ATTR_ENTITY_ID: ["light.a"], ATTR_AREA_ID: ["kitchen"], "person_id": ["person.bob"]})
    assert uut.direct() == Target({ATTR_ENTITY_ID: ["light.a"]})
    assert uut.direct(keep_selectors=True) == Target({ATTR_ENTITY_ID: ["light.a"], ATTR_AREA_ID: ["kitchen"]})


def test_target_direct_keeps_selector_specific_data() -> None:
    uut = Target({ATTR_AREA_ID: ["kitchen"], "person_id": ["person.bob"]}, target_data={"x": 1}, target_specific_data=True)
    assert uut.direct().target_specific_data == {}
    assert uut.direct(keep_selectors=True).target_specific_data == {(ATTR_AREA_ID, "kitchen"): {"x": 1}}


def test_target_selectors_only_resolved_when_included() -> None:
    uut = Target({ATTR_AREA_ID: ["kitchen"]})
    assert not uut.has_resolved_target()
    assert uut.has_resolved_target(include_selectors=True)
    assert not Target({"person_id": ["person.bob"]}).has_resolved_target(include_selectors=True)


# ---------------------------------------------------------------------------
# HomeAssistantAPI: discovery and resolution
# ---------------------------------------------------------------------------


def test_service_accepts_target_selectors_from_cached_descriptions(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    uut._service_descriptions = {
        "notify": {
            "send_message": {"fields": {}, "target": {"entity": [{"domain": ["notify"]}]}},
            "legacy_thing": {"fields": {"target": {}}},
        }
    }
    assert uut.service_accepts_target_selectors("notify.send_message") is True
    assert uut.service_accepts_target_selectors("notify.legacy_thing") is False
    assert uut.service_accepts_target_selectors("notify.unknown") is None
    assert uut.service_accepts_target_selectors("no_dot") is None
    assert uut.service_accepts_target_selectors(None) is None


def test_service_accepts_target_selectors_falls_back_to_hass_cache(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    with patch(
        "custom_components.supernotify.hass_api.async_get_cached_service_description",
        return_value={"target": {"entity": []}},
    ) as cached:
        assert uut.service_accepts_target_selectors("kodi.call_method") is True
    cached.assert_called_once_with(hass, "kodi", "call_method")


def test_service_accepts_target_selectors_survives_cache_errors(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    with patch("custom_components.supernotify.hass_api.async_get_cached_service_description", side_effect=RuntimeError("boom")):
        assert uut.service_accepts_target_selectors("kodi.call_method") is None


async def test_load_service_descriptions(hass: HomeAssistant) -> None:
    uut = HomeAssistantAPI(hass)
    descriptions = {"tts": {"speak": {"target": {"entity": []}}}}
    with patch("custom_components.supernotify.hass_api.async_get_all_descriptions", AsyncMock(return_value=descriptions)):
        await uut.load_service_descriptions()
    assert uut.service_accepts_target_selectors("tts.speak") is True


async def test_load_service_descriptions_tolerates_failure(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    uut = HomeAssistantAPI(hass)
    with patch(
        "custom_components.supernotify.hass_api.async_get_all_descriptions", AsyncMock(side_effect=RuntimeError("boom"))
    ):
        await uut.load_service_descriptions()
    assert uut._service_descriptions == {}
    assert "Unable to load action descriptions" in caplog.text


async def test_load_service_descriptions_skipped_without_hass() -> None:
    uut = HomeAssistantAPI(Mock(services=None))
    with patch("custom_components.supernotify.hass_api.async_get_all_descriptions", AsyncMock()) as loader:
        await uut.load_service_descriptions()
    loader.assert_not_called()


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
# Delivery: discovery and target selection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("option", "discovered", "expected"),
    [
        (TARGET_SELECTORS_NATIVE, None, True),
        (TARGET_SELECTORS_NATIVE, False, True),
        (TARGET_SELECTORS_RESOLVE, True, False),
        ("auto", True, True),
        ("auto", False, False),
        ("auto", None, False),
        (None, True, True),
        (None, None, False),
        ("garbage", True, True),
    ],
)
async def test_delivery_discovers_target_selectors(
    mock_context: Context, option: str | None, discovered: bool | None, expected: bool
) -> None:
    mock_context.hass_api.service_accepts_target_selectors = Mock(return_value=discovered)
    conf = {CONF_OPTIONS: {OPTION_TARGET_SELECTORS: option}} if option else {}
    uut = Delivery("unit_testing", conf, NotifyEntityTransport(mock_context, {}))
    assert uut.passes_target_selectors is False
    assert await uut.initialize(mock_context)
    assert uut.passes_target_selectors is expected


async def test_delivery_warns_on_unknown_target_selectors_option(
    mock_context: Context, caplog: pytest.LogCaptureFixture
) -> None:
    mock_context.hass_api.service_accepts_target_selectors = Mock(return_value=None)
    uut = Delivery(
        "unit_testing", {CONF_OPTIONS: {OPTION_TARGET_SELECTORS: "garbage"}}, NotifyEntityTransport(mock_context, {})
    )
    await uut.initialize(mock_context)
    assert "unknown target_selectors option garbage" in caplog.text


async def test_delivery_selection_drops_selectors_unless_passed_through() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    target = Target({ATTR_ENTITY_ID: ["notify.pong", "light.nope"], ATTR_AREA_ID: ["kitchen"], ATTR_LABEL_ID: ["chimes"]})

    uut.passes_target_selectors = False
    assert uut.select_targets(target) == Target(["notify.pong"])

    # selectors are neither category-filtered nor regex-filtered when passed through
    uut.passes_target_selectors = True
    assert uut.select_targets(target) == Target({
        ATTR_ENTITY_ID: ["notify.pong"],
        ATTR_AREA_ID: ["kitchen"],
        ATTR_LABEL_ID: ["chimes"],
    })


async def test_tts_and_chime_default_to_local_resolution() -> None:
    ctx = TestingContext(
        deliveries={
            "speak": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_ACTION: "tts.speak"},
            "ding": {CONF_TRANSPORT: TRANSPORT_CHIME},
        }
    )
    await ctx.test_initialize()
    assert ctx.delivery("speak").options[OPTION_TARGET_SELECTORS] == TARGET_SELECTORS_RESOLVE
    assert ctx.delivery("ding").options[OPTION_TARGET_SELECTORS] == TARGET_SELECTORS_RESOLVE
    assert ctx.delivery("speak").passes_target_selectors is False
    assert ctx.delivery("ding").passes_target_selectors is False


# ---------------------------------------------------------------------------
# Notification: target generation end to end
# ---------------------------------------------------------------------------


async def _generic_context(**options: str) -> TestingContext:
    ctx = TestingContext(
        deliveries={
            "chatty": {
                CONF_ACTION: "custom.tweak",
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_OPTIONS: dict(options),
            }
        }
    )
    await ctx.test_initialize()
    return ctx


async def test_generate_targets_resolves_area_to_entities() -> None:
    ctx = await _generic_context(**{OPTION_TARGET_SELECTORS: TARGET_SELECTORS_RESOLVE})
    delivery = ctx.delivery("chatty")
    resolution = TargetSelectorResolution(entity_ids=["custom.light_1", "custom.switch_2"])
    with patch.object(ctx.hass_api, "resolve_target_selectors", return_value=resolution) as resolver:
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchen"], ATTR_ENTITY_ID: ["custom.switch_2"]})
        targets: list[Target] = uut.generate_targets(delivery)
    resolver.assert_called_once_with(area_ids=["kitchen"], floor_ids=[], label_ids=[])
    assert len(targets) == 1
    # deduped against the explicit entity target, and the selector itself dropped
    assert targets[0].entity_ids == ["custom.switch_2", "custom.light_1"]
    assert targets[0].area_ids == []


async def test_generate_targets_passes_selectors_through_natively() -> None:
    ctx = await _generic_context(**{OPTION_TARGET_SELECTORS: TARGET_SELECTORS_NATIVE})
    delivery = ctx.delivery("chatty")
    resolution = TargetSelectorResolution(entity_ids=["custom.light_1"])
    with patch.object(ctx.hass_api, "resolve_target_selectors", return_value=resolution):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchen"], ATTR_FLOOR_ID: ["ground"]})
        targets: list[Target] = uut.generate_targets(delivery)
    assert len(targets) == 1
    assert targets[0].entity_ids == []
    assert targets[0].area_ids == ["kitchen"]
    assert targets[0].floor_ids == ["ground"]


async def test_generate_targets_warns_on_unknown_selectors(caplog: pytest.LogCaptureFixture) -> None:
    ctx = await _generic_context()
    delivery = ctx.delivery("chatty")
    resolution = TargetSelectorResolution(missing_areas=["kitchn"], missing_labels=["chime"])
    with patch.object(ctx.hass_api, "resolve_target_selectors", return_value=resolution):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchn"], ATTR_LABEL_ID: ["chime"]})
        targets: list[Target] = uut.generate_targets(delivery)
    assert targets[0].entity_ids == []
    assert targets[0].area_ids == []
    assert "Unknown target selectors for delivery chatty: areas ['kitchn'], floors [], labels ['chime']" in caplog.text


async def test_generate_envelopes_for_native_selectors_when_target_required() -> None:
    ctx = TestingContext(
        deliveries={
            "chatty": {
                CONF_ACTION: "custom.tweak",
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_TARGET_REQUIRED: "always",
                CONF_OPTIONS: {OPTION_TARGET_SELECTORS: TARGET_SELECTORS_NATIVE},
            },
            "quiet": {
                CONF_ACTION: "custom.tweak",
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_TARGET_REQUIRED: "always",
                CONF_OPTIONS: {OPTION_TARGET_SELECTORS: TARGET_SELECTORS_RESOLVE},
            },
        }
    )
    await ctx.test_initialize()
    with patch.object(ctx.hass_api, "resolve_target_selectors", return_value=TargetSelectorResolution()):
        uut = Notification(ctx, "testing 123", target={ATTR_AREA_ID: ["kitchen"]})
        native = uut.generate_envelopes(ctx.delivery("chatty"), uut.generate_targets(ctx.delivery("chatty")))
        resolved = uut.generate_envelopes(ctx.delivery("quiet"), uut.generate_targets(ctx.delivery("quiet")))
    assert len(native) == 1
    assert native[0].target.area_ids == ["kitchen"]
    # nothing in the area, and selectors don't pass through, so no envelope at all
    assert resolved == []


async def test_delivery_override_target_resolves_selectors() -> None:
    ctx = await _generic_context()
    delivery = ctx.delivery("chatty")
    resolution = TargetSelectorResolution(entity_ids=["custom.light_1"])
    with patch.object(ctx.hass_api, "resolve_target_selectors", return_value=resolution):
        uut = Notification(
            ctx,
            "testing 123",
            target=["custom.switch_9"],
            action_data={CONF_DELIVERY: {"chatty": {CONF_TARGET: {ATTR_LABEL_ID: ["lights"]}}}},
        )
        targets: list[Target] = uut.generate_targets(delivery)
    assert targets[0].entity_ids == ["custom.light_1"]
    assert targets[0].label_ids == []


# ---------------------------------------------------------------------------
# Transport: native pass through of selectors in the action target
# ---------------------------------------------------------------------------


async def test_notify_entity_passes_selectors_to_action(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config
    uut = NotifyEntityTransport(context)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    delivery = Delivery(
        "ping", {CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY, CONF_OPTIONS: {OPTION_TARGET_SELECTORS: "native"}}, uut
    )
    await delivery.initialize(context)
    assert delivery.passes_target_selectors
    assert await uut.deliver(
        Envelope(
            delivery,
            Notification(context, message="hello there"),
            target=Target({ATTR_ENTITY_ID: ["notify.pong"], ATTR_AREA_ID: ["kitchen"], ATTR_LABEL_ID: ["phones"]}),
        )
    )
    context.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "hello there"},
        target={ATTR_ENTITY_ID: ["notify.pong"], ATTR_AREA_ID: ["kitchen"], ATTR_LABEL_ID: ["phones"]},
        debug=False,
        context=None,
    )


async def test_notify_entity_delivers_on_selectors_alone(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config
    uut = NotifyEntityTransport(context)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    delivery = Delivery(
        "ping", {CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY, CONF_OPTIONS: {OPTION_TARGET_SELECTORS: "native"}}, uut
    )
    await delivery.initialize(context)
    assert await uut.deliver(
        Envelope(delivery, Notification(context, message="hello there"), target=Target({ATTR_AREA_ID: ["kitchen"]}))
    )
    context.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "hello there"},
        target={ATTR_AREA_ID: ["kitchen"]},
        debug=False,
        context=None,
    )


async def test_notify_entity_ignores_selectors_when_resolving(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config
    uut = NotifyEntityTransport(context)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    delivery = Delivery("ping", {CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY}, uut)
    await delivery.initialize(context)
    assert not delivery.passes_target_selectors
    assert not await uut.deliver(
        Envelope(delivery, Notification(context, message="hello there"), target=Target({ATTR_AREA_ID: ["kitchen"]}))
    )
    context.hass_api.call_service.assert_not_called()


def test_action_target_helper(mock_context: Context) -> None:
    uut = NotifyEntityTransport(mock_context, {})
    delivery = Delivery("ping", {}, uut)
    envelope = Envelope(delivery, Notification(mock_context, message="x"), target=Target({ATTR_AREA_ID: ["kitchen"]}))
    assert uut.action_target(envelope, ["notify.a"]) == {ATTR_ENTITY_ID: ["notify.a"]}
    assert uut.action_target(envelope, []) == {ATTR_ENTITY_ID: []}
    assert not uut.has_action_target(uut.action_target(envelope, []))
    delivery.passes_target_selectors = True
    assert uut.action_target(envelope, ["notify.a"]) == {ATTR_ENTITY_ID: ["notify.a"], ATTR_AREA_ID: ["kitchen"]}
    assert uut.action_target(envelope) == {ATTR_AREA_ID: ["kitchen"]}
    assert uut.has_action_target(uut.action_target(envelope))
