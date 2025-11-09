from typing import Any
from unittest.mock import Mock

from homeassistant.const import CONF_ACTION, CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.supernotify import (
    CONF_DELIVERY_DEFAULTS,
    CONF_SELECTION,
    CONF_TRANSPORT,
    SELECTION_BY_SCENARIO,
    TRANSPORT_ALEXA,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_EMAIL,
    TRANSPORT_GENERIC,
    TRANSPORT_PERSISTENT,
    TRANSPORT_SMS,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.transports.generic import GenericTransport

from .hass_setup_lib import TestingContext

DELIVERY: dict[str, Any] = {
    "email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_TRANSPORT: TRANSPORT_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_devices": {CONF_TRANSPORT: TRANSPORT_ALEXA, CONF_ACTION: "notify.send_message"},
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_SELECTION: [SELECTION_BY_SCENARIO]},
}


async def test_simple_create_with_defined_default_delivery() -> None:
    ctx = TestingContext(deliveries=DELIVERY, transport_types=[GenericTransport])
    ctx.deliveries["chat"]["default"] = True
    await ctx.test_initialize()

    assert list(ctx.delivery_registry.deliveries.keys()) == ["chat"]
    assert ctx.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC] is not None
    assert ctx.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC].name == "chat"


async def test_simple_create_with_defined_delivery() -> None:
    context = TestingContext(deliveries=DELIVERY, transport_types=[GenericTransport])
    await context.test_initialize()

    assert list(context.delivery_registry.deliveries.keys()) == ["chat"]
    assert context.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC] is not None
    assert context.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC].name == "DEFAULT_generic"


async def test_simple_create_with_only_default_deliveries(mock_context: Context) -> None:
    ctx = TestingContext(deliveries={}, transport_types=[GenericTransport])
    await ctx.test_initialize()

    assert list(ctx.delivery_registry.deliveries.keys()) == []
    assert ctx.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC] is not None
    assert ctx.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC].name == "DEFAULT_generic"


async def test_default_delivery_defaulted() -> None:
    context = TestingContext(
        deliveries=DELIVERY,
        transport_configs={TRANSPORT_GENERIC: {CONF_DELIVERY_DEFAULTS: {CONF_ACTION: "notify.slackity"}}},
        transport_types=[GenericTransport],
    )
    await context.test_initialize()

    assert context.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC] is not None
    assert context.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC].name == "DEFAULT_generic"
    assert context.delivery_registry.default_delivery_by_transport[TRANSPORT_GENERIC].action == "notify.slackity"


async def test_transport_defaults_used_for_missing_service(hass: HomeAssistant, uninitialized_unmocked_config: Context) -> None:
    delivery = {"chatty": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_TARGET: ["chan1", "chan2"]}}
    context = uninitialized_unmocked_config
    context.delivery_registry._deliveries = delivery
    uut = GenericTransport(context, delivery_defaults={CONF_ACTION: "notify.slackity"})
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    await context.delivery_registry.initialize(context)

    await uut.initialize()
    assert list(uut.delivery_registry.deliveries.keys()) == ["chatty"]
    assert uut.delivery_registry.deliveries["chatty"].action == "notify.slackity"


def test_simplify_text(mock_context: Context) -> None:
    from custom_components.supernotify.transports.generic import GenericTransport

    uut = GenericTransport(mock_context)
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>", strip_urls=True)
        == "Hello world! Visit it's great 100 test"
    )
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>")
        == "Hello world! Visit https://example.com it's great 100 test"
    )
    assert uut.simplify("NoSpecialChars123") == "NoSpecialChars123"


async def test_device_discovery(unmocked_config: Context) -> None:
    uut = GenericTransport(unmocked_config, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target is None
    dev: DeviceEntry = Mock(spec=DeviceEntry, id="abc123")
    unmocked_config.hass_api.discover_devices = Mock(  # type: ignore
        return_value=[dev]
    )

    uut = GenericTransport(unmocked_config, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target is not None
    assert uut.delivery_defaults.target.device_ids == [dev.id]
