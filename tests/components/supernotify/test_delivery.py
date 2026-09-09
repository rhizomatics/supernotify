from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

from homeassistant.const import ATTR_ENTITY_ID, CONF_ACTION, CONF_CONDITIONS

from custom_components.supernotify.const import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    OCCUPANCY_ALL,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import DeviceInfo
from custom_components.supernotify.model import Target
from custom_components.supernotify.transports.alexa_devices import AlexaDevicesTransport
from custom_components.supernotify.transports.chime import ChimeTransport
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.media_player import MediaPlayerTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport

from .hass_setup_lib import MockGroup, TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.context import Context


async def test_target_selection() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    assert uut.select_targets(Target(["notify.pong", "weird_generic_a", "notify"])) == Target(["notify.pong"])


async def test_target_selection_expands_group_and_filters_members() -> None:
    ctx = TestingContext(
        transport_types=[NotifyEntityTransport],
        entities={"group.mixed": MockGroup(["notify.phone_1", "switch.bell", "notify.phone_2"])},
    )
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    assert uut.select_targets(Target(["group.mixed"])).entity_ids == ["notify.phone_1", "notify.phone_2"]


async def test_target_selection_expands_platform_group() -> None:
    ctx = TestingContext(
        transport_types=[MediaPlayerTransport],
        entities={"media_player.all_speakers": MockGroup(["media_player.kitchen", "media_player.hall"])},
    )
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, MediaPlayerTransport(ctx, {}))
    assert uut.select_targets(Target(["media_player.all_speakers"])).entity_ids == ["media_player.kitchen", "media_player.hall"]


async def test_target_selection_keeps_group_id_when_selector_accepts_it_but_not_members() -> None:
    ctx = TestingContext(
        transport_types=[AlexaDevicesTransport],
        entities={"group.alexa": MockGroup(["media_player.echo_1", "media_player.echo_2"])},
    )
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, AlexaDevicesTransport(ctx, {}))
    assert uut.select_targets(Target(["group.alexa", "media_player.echo_3"])).entity_ids == ["group.alexa"]


async def test_target_selection_propagates_group_data_to_members() -> None:
    ctx = TestingContext(
        transport_types=[NotifyEntityTransport],
        entities={"group.phones": MockGroup(["notify.phone_1", "notify.phone_2"])},
    )
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    target = Target(["group.phones"], target_data={"ttl": 5}, target_specific_data=True)
    selected = uut.select_targets(target)
    assert selected.entity_ids == ["notify.phone_1", "notify.phone_2"]
    assert selected.target_specific_data == {
        (ATTR_ENTITY_ID, "notify.phone_1"): {"ttl": 5},
        (ATTR_ENTITY_ID, "notify.phone_2"): {"ttl": 5},
    }


async def test_target_selection_leaves_unknown_group_alone() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport, ChimeTransport])
    await ctx.test_initialize()
    # group has no state so cannot be expanded, ordinary selector rules apply
    assert Delivery("a", {}, NotifyEntityTransport(ctx, {})).select_targets(Target(["group.nowhere"])).entity_ids == []
    assert Delivery("b", {}, ChimeTransport(ctx, {})).select_targets(Target(["group.nowhere"])).entity_ids == ["group.nowhere"]


async def test_target_selection_dedupes_member_and_group() -> None:
    ctx = TestingContext(
        transport_types=[NotifyEntityTransport],
        entities={"group.phones": MockGroup(["notify.phone_1", "notify.phone_2"])},
    )
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, NotifyEntityTransport(ctx, {}))
    assert uut.select_targets(Target(["notify.phone_2", "group.phones"])).entity_ids == ["notify.phone_2", "notify.phone_1"]


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
