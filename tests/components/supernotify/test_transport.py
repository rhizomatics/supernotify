from unittest.mock import Mock

from homeassistant.const import CONF_DEBUG
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.device_registry import DeviceEntry

from custom_components.supernotify import (
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.generic import GenericTransport

from .doubles_lib import DummyService
from .hass_setup_lib import TestingContext


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
    uut = GenericTransport(unmocked_config, {CONF_DEVICE_DOMAIN: ["unit_testing"], CONF_DEVICE_DISCOVERY: True})
    await uut.initialize()
    assert uut.delivery_defaults.target is None
    dev: DeviceEntry = Mock(spec=DeviceEntry, id="11112222ffffeeee00009999ddddcccc")
    unmocked_config.hass_api.discover_devices = Mock(  # type: ignore
        return_value=[dev]
    )

    uut = GenericTransport(unmocked_config, {CONF_DEVICE_DOMAIN: ["unit_testing"], CONF_DEVICE_DISCOVERY: True})
    await uut.initialize()
    assert uut.delivery_defaults.target is not None
    assert uut.delivery_defaults.target.device_ids == [dev.id]


async def test_call_action_simple(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    dummy_service = DummyService(hass)
    envelope = Envelope(
        Delivery("testing", {}, uut),
        Notification(ctx),
    )
    response = await uut.call_action(envelope, "notify.custom_test", {"message": "hello"}, None, False)
    assert response is True
    await hass.async_block_till_done()
    assert len(dummy_service.calls) > 0
    service_call = dummy_service.calls[0]
    assert service_call.domain == "notify"
    assert service_call.service == "custom_test"
    assert service_call.data == {"message": "hello"}
    assert service_call.hass == hass

    assert len(envelope.calls) == 1


async def test_call_action_debug(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    dummy_service = DummyService(hass, response={"test": "debug_001"}, supports_response=SupportsResponse.ONLY)
    envelope = Envelope(
        Delivery("testing", {CONF_DEBUG: True}, uut),
        Notification(ctx),
    )
    response = await uut.call_action(envelope, "notify.custom_test", {"message": "hello"}, None, False)
    assert response is True
    await hass.async_block_till_done()
    assert len(dummy_service.calls) > 0
    service_call = dummy_service.calls[0]
    assert service_call.domain == "notify"
    assert service_call.service == "custom_test"
    assert service_call.data == {"message": "hello"}
    assert service_call.hass == hass

    assert len(envelope.calls) == 1
    assert envelope.calls[0].service_response == {"test": "debug_001"}


async def test_call_action_debug_no_response(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    _dummy_service = DummyService(hass, supports_response=SupportsResponse.NONE)
    envelope = Envelope(
        Delivery("testing", {CONF_DEBUG: True}, uut),
        Notification(ctx),
    )
    response = await uut.call_action(envelope, "notify.custom_test", {"message": "hello"}, None, False)
    assert response is True
    await hass.async_block_till_done()

    assert len(envelope.calls) == 1
    assert envelope.calls[0].service_response is None


async def test_call_action_debug_failing_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    _dummy_service = DummyService(hass, exception=NotImplementedError("not available"))
    envelope = Envelope(
        Delivery("testing", {CONF_DEBUG: True}, uut),
        Notification(ctx),
    )
    response: bool = await uut.call_action(envelope, "notify.custom_test", {"message": "hello"}, None, False)
    assert response is False
