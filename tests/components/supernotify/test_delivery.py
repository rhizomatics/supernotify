from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import CONF_ACTION, CONF_CONDITIONS
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_OCCUPANCY,
    CONF_TEMPLATE,
    CONF_TRANSPORT,
    INCLUSION_DEFAULT,
    OCCUPANCY_ALL,
    OCCUPANCY_ALL_IN,
    PRIORITY_VALUES,
    TRANSPORT_GENERIC,
    TRANSPORT_NTFY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import TrackedDeviceDetails
from custom_components.supernotify.model import Target
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.mqtt import MQTTTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport

from .hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.context import Context


async def test_target_selection() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    assert uut.select_targets(Target(["notify.pong", "weird_generic_a", "notify"])) == Target(["notify.pong"])


async def test_target_selection_always_allows_own_delivery_or_transport_name() -> None:
    """A target category matching either the delivery's own name or its transport's name

    always survives selection, even though neither is in the transport's own
    OPTION_TARGET_CATEGORIES. The two serve different purposes and both stay available:
    - the TRANSPORT name (`notify_entity:value`) reaches every delivery of that transport,
      so scenario/time/occupancy selection logic can still decide which one actually fires
    - a specific DELIVERY name (`unit_testing:value`) pins the target to just that one
      delivery, for when two deliveries of the same transport must stay distinct

    Note: `Target.__eq__` only compares the fixed standard categories (entity_id, email,
    etc.), silently ignoring custom ones - so assertions here must use `for_category()`,
    not `==`, to actually exercise custom-category filtering.
    """
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()

    # a custom-named delivery still gets its transport's name for free (broadcast)
    custom_named = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    assert custom_named.select_targets(Target({"notify_entity": ["notify.freeform"]})).for_category("notify_entity") == [
        "notify.freeform"
    ]

    # ...and also gets through when the category matches its own (delivery) name
    assert custom_named.select_targets(Target({"unit_testing": ["notify.freeform"]})).for_category("unit_testing") == [
        "notify.freeform"
    ]

    # a delivery named after its transport (the auto-configured/default case) still works
    default_named = Delivery("notify_entity", {}, NotifyEntityTransport(ctx, {}))
    assert default_named.select_targets(Target({"notify_entity": ["notify.freeform"]})).for_category("notify_entity") == [
        "notify.freeform"
    ]


async def test_target_selection_delivery_scoped_value_reaches_only_that_delivery() -> None:
    """A value qualified with a custom delivery's own name survives selection for exactly

    that delivery, and does not leak into a differently-named delivery of the same
    transport (unlike a category matching the transport's own name, which is meant to
    reach every delivery of that transport). Transports read `resolved_targets()` rather
    than a typed getter like `.email`, so this doesn't depend on the value being
    reclassified into a standard category - it survives under its own qualified name.
    """
    ctx = TestingContext(transport_types=[EmailTransport])
    await ctx.test_initialize()
    transport = EmailTransport(ctx, {})

    html_email = Delivery("html_email", {CONF_ACTION: "notify.smtp"}, transport)
    result = html_email.select_targets(Target({"html_email": ["bigdave@34acacia.avenue.com"]}))
    assert result.resolved_targets() == ["bigdave@34acacia.avenue.com"]

    plain_email = Delivery("email", {CONF_ACTION: "notify.smtp"}, transport)
    leaked = plain_email.select_targets(Target({"html_email": ["bigdave@34acacia.avenue.com"]}))
    assert leaked.resolved_targets() == []


async def test_reclassify_unqualified_target_falls_back_to_primary_category() -> None:
    """A value with no shape any validator recognises (e.g. an MQTT topic) still reaches

    its transport when set directly on a delivery's own `target:` - `Delivery.
    reclassify_unqualified_target()` reclassifies it into the delivery's first plain-string
    `target_categories` entry, since there's no ambiguity about which delivery a
    delivery-scoped value belongs to (unlike a blended, notification-level target list).
    """
    ctx = TestingContext(transport_types=[MQTTTransport])
    await ctx.test_initialize()
    uut = Delivery("broker", {CONF_ACTION: "mqtt.publish"}, MQTTTransport(ctx, {}))

    unqualified = Target(["notify/queue/1"])
    assert unqualified.custom_ids(Target.UNKNOWN_CUSTOM_CATEGORY) == ["notify/queue/1"]

    resolved = uut.reclassify_unqualified_target(unqualified)
    assert resolved.custom_ids("topic") == ["notify/queue/1"]
    assert resolved.custom_ids(Target.UNKNOWN_CUSTOM_CATEGORY) == []

    # a value that already matches a real category (or a delivery with no plain-string
    # category to fall back on at all) passes through unchanged
    already_categorised = Target(["me@house.org"])
    assert uut.reclassify_unqualified_target(already_categorised).email == ["me@house.org"]


async def test_reclassify_unqualified_target_warns_when_genuinely_unmappable(caplog: pytest.LogCaptureFixture) -> None:
    """A delivery with only `TargetEntityCategory`-constrained categories (no plain-string one to

    fall back on) has nowhere to put an unqualified value - since it's already established
    as exclusively scoped to this one delivery, this is a real, actionable warning, not a
    false positive from a value meant for a different delivery.
    """
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = Delivery("notify_entity", {CONF_ACTION: "notify.send_message"}, NotifyEntityTransport(ctx, {}))

    with caplog.at_level(logging.WARNING):
        resolved = uut.reclassify_unqualified_target(Target(["not_an_entity_id"]))

    assert resolved.custom_ids(Target.UNKNOWN_CUSTOM_CATEGORY) == ["not_an_entity_id"]
    assert any("no target category" in r.message for r in caplog.records)


async def test_delivery_config_level_target_reclassified_to_transport_category() -> None:
    """A bare, unqualified `target:` set directly in a delivery's own YAML config is

    reclassified at `Delivery` construction time, so it survives `select_targets()`
    without needing the transport to special-case the uncategorised bucket.
    """
    ctx = TestingContext(transport_types=[MQTTTransport])
    await ctx.test_initialize()
    uut = Delivery("broker", {CONF_ACTION: "mqtt.publish", "target": "notify/queue/1"}, MQTTTransport(ctx, {}))
    assert uut.target is not None
    assert uut.target.custom_ids("topic") == ["notify/queue/1"]


async def test_delivery_config_level_target_reclassified_to_configured_category() -> None:
    """A delivery's own `OPTION_TARGET_CATEGORIES` (e.g. a made-up category for the

    bring-your-own-categories `generic` transport) takes precedence over the transport's
    own declared primary category (`generic` has none at all) when reclassifying a bare,
    unqualified `target:` set directly on the delivery.
    """
    ctx = TestingContext(transport_types=[GenericTransport])
    await ctx.test_initialize()
    uut = Delivery(
        "slack",
        {
            CONF_ACTION: "notify.my_slack_service",
            "target": "A20H2AN55DX",
            "options": {"target_categories": "slack_channel"},
        },
        GenericTransport(ctx, {}),
    )
    assert uut.target is not None
    assert uut.target.custom_ids("slack_channel") == ["A20H2AN55DX"]


async def test_delivery_config_level_target_left_unqualified_when_explicitly_configured() -> None:
    """If a delivery's own `OPTION_TARGET_CATEGORIES` explicitly lists the uncategorised

    bucket itself, that's a deliberate choice to accept unqualified values as-is - a bare
    `target:` must NOT be relabelled into some other configured category instead.
    """
    ctx = TestingContext(transport_types=[GenericTransport])
    await ctx.test_initialize()
    uut = Delivery(
        "chatty",
        {
            CONF_ACTION: "notify.slackity",
            "target": ["chan1", "chan2"],
            "options": {"target_categories": ["entity_id", Target.UNKNOWN_CUSTOM_CATEGORY]},
        },
        GenericTransport(ctx, {}),
    )
    assert uut.target is not None
    assert uut.target.custom_ids(Target.UNKNOWN_CUSTOM_CATEGORY) == ["chan1", "chan2"]


async def test_simple_create(mock_context: Context) -> None:
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(mock_context, {}))
    assert await uut.initialize(mock_context)
    assert uut.name == "unit_testing"
    assert uut.enabled is True
    assert uut.occupancy == OCCUPANCY_ALL
    assert uut.message is None
    assert uut.title is None
    assert uut.template is None
    assert uut.alias is None
    assert uut.conditions is None
    assert uut.priority == list(PRIORITY_VALUES.keys())
    assert uut.inclusion == [INCLUSION_DEFAULT]
    assert uut.transport.name == "notify_entity"
    assert uut.data == {}
    assert uut.options == uut.transport.delivery_defaults.options
    assert uut.action == "notify.send_message"
    assert uut.target is None


async def test_broken_create_using_reserved_word(mock_context: Context) -> None:
    uut = Delivery("ALL", {}, NotifyEntityTransport(mock_context))
    assert await uut.initialize(mock_context) is False
    mock_context.hass_api.raise_issue.assert_called_with(  # type: ignore
        "delivery_ALL_reserved_name",
        issue_key="delivery_reserved_name",
        issue_map={"delivery": "ALL"},
        learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
    )


async def test_broken_create_with_missing_action(mock_context: Context) -> None:
    uut = Delivery("generic", {}, GenericTransport(mock_context))
    assert await uut.initialize(mock_context) is False
    mock_context.hass_api.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_action",
        issue_key="delivery_invalid_action",
        issue_map={"action": "", "delivery": "generic"},
        learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
    )


async def test_repair_for_bad_conditions(mock_context: Context) -> None:
    mock_context.hass_api.build_conditions = AsyncMock(side_effect=Exception("integrations"))  # type: ignore
    uut = Delivery(
        "generic",
        {CONF_CONDITIONS: [{"condition": "xor"}]},
        GenericTransport(mock_context, {CONF_DELIVERY_DEFAULTS: {CONF_ACTION: "notify.notify"}}),
    )
    assert await uut.initialize(mock_context) is False
    mock_context.hass_api.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_condition",
        issue_key="delivery_invalid_condition",
        issue_map={"delivery": "generic", "condition": "[{'condition': 'xor'}]", "exception": "integrations"},
        learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
    )


async def test_delivery_inherits_transport_delivery_defaults(mock_context: Context) -> None:
    transport = GenericTransport(
        mock_context,
        {
            CONF_DELIVERY_DEFAULTS: {
                CONF_ACTION: "notify.notify",
                CONF_TEMPLATE: "transport_template",
                CONF_OCCUPANCY: OCCUPANCY_ALL_IN,
            }
        },
    )
    uut = Delivery("generic", {}, transport)
    assert uut.template == "transport_template"
    assert uut.occupancy == OCCUPANCY_ALL_IN


async def test_delivery_overrides_transport_delivery_defaults(mock_context: Context) -> None:
    transport = GenericTransport(
        mock_context,
        {
            CONF_DELIVERY_DEFAULTS: {
                CONF_ACTION: "notify.notify",
                CONF_TEMPLATE: "transport_template",
                CONF_OCCUPANCY: OCCUPANCY_ALL_IN,
            }
        },
    )
    uut = Delivery("generic", {CONF_TEMPLATE: "delivery_template"}, transport)
    assert uut.template == "delivery_template"
    # not overridden at delivery level, so still inherited from the transport
    assert uut.occupancy == OCCUPANCY_ALL_IN


async def test_autogenerate_default_vs_explicit_selection(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)
    er.async_get(hass).async_get_or_create("notify", "alexa_devices", "bedroom_echo_unique_id")
    MockConfigEntry(domain="ntfy", data={}).add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()

    # both are named plainly after their transport, regardless of selection
    # an Alexa device target is well-defined enough to fire by default
    assert "alexa_devices" in ctx.delivery_registry.deliveries
    assert "alexa_devices" in [d.name for d in ctx.delivery_registry.implicit_deliveries]
    # opaque per-delivery identifier (ntfy_device_id) -> explicit-only
    assert "ntfy" in ctx.delivery_registry.deliveries
    assert "ntfy" not in [d.name for d in ctx.delivery_registry.implicit_deliveries]


async def test_autogenerate_skips_on_name_collision(hass: HomeAssistant, mock_context: Context) -> None:
    """A transport's name is reserved for its own delivery - a delivery configured for a
    *different* transport can't also use it. The misnamed delivery is rejected (with a
    repair issue raised) and the auto-configured delivery for the actual "ntfy" transport
    takes the name instead."""
    MockConfigEntry(domain="ntfy", data={}).add_to_hass(hass)

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"ntfy": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.notify"}},
    )
    await ctx.test_initialize()
    uut = Delivery("ntfy", {}, GenericTransport(mock_context))

    await uut.initialize(ctx)
    assert ctx.delivery_registry.deliveries["ntfy"].transport.name == TRANSPORT_NTFY
    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, "delivery_ntfy_reserved_name") is not None


def test_device_discovery(unmocked_config: Context) -> None:
    uut = Delivery(
        "devicey",
        {},
        transport=GenericTransport(unmocked_config, {CONF_DEVICE_DOMAIN: ["unit_testing"], CONF_DEVICE_DISCOVERY: True}),
    )

    dev: TrackedDeviceDetails = Mock(spec=TrackedDeviceDetails, device_id="11112222ffffeeee00009999ddddcccc")
    unmocked_config.hass_api.discover_devices = Mock(  # type: ignore
        return_value=[dev]
    )
    uut.discover_devices(unmocked_config)
    assert uut.target.device_ids == [dev.device_id]  # type: ignore
