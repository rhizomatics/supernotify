from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import CONF_ACTION, CONF_CONDITIONS

from custom_components.supernotify.const import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_TRANSPORT,
    EMAIL_OPTION_MODE_DIRECT,
    OCCUPANCY_ALL,
    OPTION_MODE,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
    TRANSPORT_EMAIL,
    TRANSPORT_SMTP,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import DeviceInfo
from custom_components.supernotify.model import Target
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport

from .hass_setup_lib import TestingContext

if TYPE_CHECKING:
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


def test_smtp_transport_deprecation_normalizes_to_email(mock_context: Context, caplog: pytest.LogCaptureFixture) -> None:
    """The old `smtp` transport was folded into `email` - a delivery still configured with
    `transport: smtp` should be normalized in place to `transport: email`, with a warning, and
    switched to direct-connection mode - even with no `options:` block of its own, which is the
    common case for a bare `transport: smtp` delivery and previously left self.options untouched
    (conf.get(CONF_OPTIONS, {}) returns a fresh dict when conf has no options key, so writing to
    conf[CONF_OPTIONS] afterwards didn't reach the live self.options actually used at send time)."""
    conf = {CONF_TRANSPORT: TRANSPORT_SMTP}
    caplog.clear()
    uut = Delivery("legacy_smtp", conf, EmailTransport(mock_context, {}))
    assert conf[CONF_TRANSPORT] == TRANSPORT_EMAIL
    assert uut.options[OPTION_MODE] == EMAIL_OPTION_MODE_DIRECT
    assert any("smtp transport" in r.message for r in caplog.records if r.levelname == "WARNING")
