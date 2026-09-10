from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

from homeassistant.const import CONF_ACTION, CONF_CONDITIONS
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify.const import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_TRANSPORT,
    OCCUPANCY_ALL,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import DeviceInfo
from custom_components.supernotify.model import Target
from custom_components.supernotify.transports.generic import GenericTransport
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
    assert uut.selection == [SELECTION_DEFAULT]
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


async def test_autogenerate_default_vs_explicit_naming(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="kodi", data={}).add_to_hass(hass)
    MockConfigEntry(domain="ntfy", data={}).add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()

    # positively-identifiable target (entity_id) -> fires by default, kept visibly distinct
    assert "DEFAULT_kodi" in ctx.delivery_registry.deliveries
    assert "DEFAULT_kodi" in [d.name for d in ctx.delivery_registry.implicit_deliveries]
    # opaque per-delivery identifier (ntfy_device_id) -> explicit-only, named plainly
    assert "ntfy" in ctx.delivery_registry.deliveries
    assert "ntfy" not in [d.name for d in ctx.delivery_registry.implicit_deliveries]


async def test_autogenerate_skips_on_name_collision(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="ntfy", data={}).add_to_hass(hass)

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"ntfy": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.notify"}},
    )
    await ctx.test_initialize()

    # the user's own "ntfy" delivery (for an unrelated transport) must not be clobbered by
    # the auto-generated ntfy-transport delivery, which would otherwise collide on the name
    assert ctx.delivery_registry.deliveries["ntfy"].transport.name == TRANSPORT_GENERIC


def test_device_discovery(unmocked_config: Context) -> None:
    uut = Delivery(
        "devicey",
        {},
        transport=GenericTransport(unmocked_config, {CONF_DEVICE_DOMAIN: ["unit_testing"], CONF_DEVICE_DISCOVERY: True}),
    )

    dev: DeviceInfo = Mock(spec=DeviceInfo, device_id="11112222ffffeeee00009999ddddcccc")
    unmocked_config.hass_api.discover_devices = Mock(  # type: ignore
        return_value=[dev]
    )
    uut.discover_devices(unmocked_config)
    assert uut.target.device_ids == [dev.device_id]  # type: ignore
