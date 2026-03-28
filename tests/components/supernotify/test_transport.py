from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from homeassistant.const import ATTR_NAME, CONF_DEBUG, CONF_ENABLED
from homeassistant.core import HomeAssistant, SupportsResponse

from custom_components.supernotify.const import CONF_DELIVERY_DEFAULTS, TRANSPORT_GENERIC
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import DeliveryConfig, Target, TransportConfig, TransportFeature
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.transports.generic import GenericTransport

from .doubles_lib import DummyService
from .hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.hass_api import HomeAssistantAPI
    from custom_components.supernotify.transport import Transport


def test_simplify_text() -> None:

    uut = GenericTransport(Mock())
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>", strip_urls=True)
        == "Hello world! Visit it's great 100 test"
    )
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>")
        == "Hello world! Visit https://example.com it's great 100 test"
    )
    assert uut.simplify("NoSpecialChars123") == "NoSpecialChars123"


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


@pytest.mark.parametrize("transport_type", TRANSPORTS)
async def test_common_features(mock_hass: HomeAssistant, mock_hass_api: HomeAssistantAPI, transport_type: Transport) -> None:
    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()

    transport = transport_type(ctx, {})  # type: ignore[operator]
    assert isinstance(transport.supported_features, TransportFeature)
    assert isinstance(transport.setup_delivery_options({}, "testing"), dict)
    assert isinstance(transport.extra_attributes(), dict)
    assert isinstance(transport.default_config, TransportConfig)
    assert isinstance(transport.targets, Target)
    attrs = transport.attributes()
    assert attrs[ATTR_NAME] == transport_type.name
    assert isinstance(attrs[CONF_ENABLED], bool)
    assert attrs[CONF_DELIVERY_DEFAULTS] == transport.delivery_defaults
    assert isinstance(transport.auto_configure(mock_hass_api), (DeliveryConfig, type(None)))


async def test_transport_base_supported_features_and_default_config(mock_hass: HomeAssistant) -> None:
    # DummyTransport doesn't override supported_features or default_config - covers base class lines 73-74, 81-82
    from tests.components.supernotify.doubles_lib import DummyTransport

    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()
    t = DummyTransport(ctx)
    assert TransportFeature.MESSAGE in t.supported_features
    assert isinstance(t.default_config, TransportConfig)


async def test_transport_attributes_with_error(mock_hass: HomeAssistant) -> None:
    # Lines 100-102: attributes includes error info after record_error
    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    uut.record_error("test error msg", "test_method")
    attrs = uut.attributes()
    assert attrs["last_error_message"] == "test error msg"
    assert attrs["last_error_in"] == "test_method"
    assert attrs["error_count"] == 1


async def test_set_action_data(mock_hass: HomeAssistant) -> None:
    # Lines 122-124: set_action_data adds key when data is not None
    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    action_data: dict = {}
    uut.set_action_data(action_data, "message", "hello")
    assert action_data["message"] == "hello"
    uut.set_action_data(action_data, "skipped", None)
    assert "skipped" not in action_data


async def test_call_action_no_action(hass: HomeAssistant) -> None:
    # Lines 141-148: skips when no action configured
    from custom_components.supernotify.model import SuppressionReason

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    envelope = Envelope(
        Delivery("testing", {}, uut),  # no action in config or transport defaults
        Notification(ctx),
    )
    result = await uut.call_action(envelope)  # no qualified_action arg
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_ACTION


async def test_call_action_missing_required_target(hass: HomeAssistant) -> None:
    # Lines 156-163: skips when target required but missing
    from custom_components.supernotify.model import SuppressionReason, TargetRequired
    from custom_components.supernotify.transports.email import EmailTransport

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    email_transport = EmailTransport(ctx)
    delivery = Delivery("email_test", {}, email_transport)
    assert delivery.target_required == TargetRequired.ALWAYS
    envelope = Envelope(delivery, Notification(ctx))
    result = await email_transport.call_action(envelope, "notify.smtp", {})
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_TARGET
