from unittest.mock import AsyncMock, Mock

from homeassistant.const import CONF_ACTION, CONF_CONDITION
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.supernotify import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    OCCUPANCY_ALL,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import Target
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport

from .hass_setup_lib import TestingContext


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
        {CONF_CONDITION: {"condition": "xor"}},
        GenericTransport(mock_context, {CONF_DELIVERY_DEFAULTS: {CONF_ACTION: "notify.notify"}}),
    )
    assert await uut.initialize(mock_context) is False
    mock_context.hass_api.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_condition",
        issue_key="delivery_invalid_condition",
        issue_map={"delivery": "generic", "condition": "{'condition': 'xor'}", "exception": "integrations"},
        learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
    )


def test_device_discovery(unmocked_config: Context) -> None:
    uut = Delivery(
        "devicey",
        {},
        transport=GenericTransport(unmocked_config, {CONF_DEVICE_DOMAIN: ["unit_testing"], CONF_DEVICE_DISCOVERY: True}),
    )

    dev: DeviceEntry = Mock(spec=DeviceEntry, id="11112222ffffeeee00009999ddddcccc")
    unmocked_config.hass_api.discover_devices = Mock(  # type: ignore
        return_value=[dev]
    )
    uut.discover_devices(unmocked_config)
    assert uut.target.device_ids == [dev.id]  # type: ignore
