from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from homeassistant.const import ATTR_NAME, CONF_DEBUG, CONF_ENABLED
from homeassistant.core import HomeAssistant, SupportsResponse

from custom_components.supernotify.const import CONF_DELIVERY_DEFAULTS, TRANSPORT_GENERIC
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.engine import TRANSPORTS
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target, TransportConfig, TransportFeature
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_media_player import AlexaMediaPlayerTransport
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


def test_simplify_text_keeps_sign_characters() -> None:
    """+, -, = and % are kept even though some of them are Unicode symbol codepoints,
    so numeric values like "+3" aren't left indistinguishable from "3"."""

    uut = GenericTransport(Mock())
    assert uut.simplify("Temperature +3 °C, -2 overnight, 50% humidity") == "Temperature +3 C, -2 overnight, 50% humidity"


def test_simplify_text_normalizes_nfd_before_stripping_marks() -> None:
    """NFD text (e.g. from macOS filenames) decomposes accents into a separate combining
    mark codepoint, which must not be stripped as if it were unrelated symbol markup."""

    uut = GenericTransport(Mock())
    nfd_text = unicodedata.normalize("NFD", "Umidità già alta")
    assert uut.simplify(nfd_text) == "Umidità già alta"


def test_simplify_text_strip_urls_does_not_match_bare_scheme_like_words() -> None:
    """A word ending in a colon (e.g. "Attention:") parses with a truthy `scheme` under
    urlparse, but is not a URL and must not be dropped."""

    uut = GenericTransport(Mock())
    assert uut.simplify("Attention: visit https://example.com now", strip_urls=True) == "Attention: visit now"


def test_simplify_text_preserves_ssml_for_spoken_transports() -> None:
    """Spoken transports pass SSML to the voice assistant, so the markup must survive."""

    uut = AlexaMediaPlayerTransport(Mock())
    assert uut.supported_features & TransportFeature.SPOKEN

    assert (
        uut.simplify('<amazon:effect name="whispered">Smoke alarm in the kitchen</amazon:effect>')
        == '<amazon:effect name="whispered">Smoke alarm in the kitchen</amazon:effect>'
    )
    assert (
        uut.simplify('<speak><break time="500ms"/>Front_door open</speak>')
        == '<speak><break time="500ms"/>Front door open</speak>'
    )
    # text around the markup is still simplified, and spacing is kept
    assert (
        uut.simplify('<speak>Front <emphasis level="strong">door</emphasis> open (again) £5</speak>')
        == '<speak>Front <emphasis level="strong">door</emphasis> open again 5</speak>'
    )
    # angle brackets that are not SSML keep the old behaviour, on any transport
    assert uut.simplify("Sensor <test> tripped") == "Sensor test tripped"


def test_simplify_text_strips_ssml_for_non_spoken_transports() -> None:
    """Transports without a voice interface have no use for SSML, so it is simplified away."""

    uut = GenericTransport(Mock())
    assert not uut.supported_features & TransportFeature.SPOKEN
    assert (
        uut.simplify('<amazon:effect name="whispered">Smoke alarm</amazon:effect>')
        == 'amazon:effect name="whispered"Smoke alarm/amazon:effect'
    )


async def test_call_action_simple(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
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
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
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
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
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
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
    _dummy_service = DummyService(hass, exception=NotImplementedError("not available"))
    envelope = Envelope(
        Delivery("testing", {CONF_DEBUG: True}, uut),
        Notification(ctx),
    )
    response: bool = await uut.call_action(envelope, "notify.custom_test", {"message": "hello"}, None, False)
    assert response is False


async def test_call_action_logs_once_while_unavailable(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """The first failure logs at ERROR; consecutive failures while still unavailable are
    downgraded to DEBUG (no log spam); a subsequent success logs a recovery message once and
    a later failure goes back to ERROR."""
    caplog.set_level(logging.DEBUG, logger="custom_components.supernotify.transport")
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
    dummy_service = DummyService(hass, exception=NotImplementedError("not available"))

    def make_envelope() -> Envelope:
        return Envelope(Delivery("testing", {CONF_DEBUG: True}, uut), Notification(ctx))

    caplog.clear()
    assert await uut.call_action(make_envelope(), "notify.custom_test", {"message": "hello"}, None, False) is False
    assert uut._unavailable is True
    assert [r.levelname for r in caplog.records if "Failed to notify" in r.message] == ["ERROR"]

    caplog.clear()
    assert await uut.call_action(make_envelope(), "notify.custom_test", {"message": "hello"}, None, False) is False
    assert [r.levelname for r in caplog.records if "Failed to notify" in r.message] == ["DEBUG"]

    caplog.clear()
    dummy_service.exception = None
    assert await uut.call_action(make_envelope(), "notify.custom_test", {"message": "hello"}, None, False) is True
    assert uut._unavailable is False
    assert any("recovered" in r.message for r in caplog.records if r.levelname == "INFO")

    caplog.clear()
    dummy_service.exception = NotImplementedError("not available")
    assert await uut.call_action(make_envelope(), "notify.custom_test", {"message": "hello"}, None, False) is False
    assert [r.levelname for r in caplog.records if "Failed to notify" in r.message] == ["ERROR"]


@pytest.mark.parametrize("transport_type", TRANSPORTS)
async def test_common_features(mock_hass: HomeAssistant, mock_hass_api: HomeAssistantAPI, transport_type: Transport) -> None:
    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()

    transport = transport_type(ctx, {})  # type: ignore[operator]  # ty: ignore[call-non-callable]
    assert isinstance(transport.supported_features, TransportFeature)
    assert isinstance(transport.setup_delivery_options({}, "testing"), dict)
    assert isinstance(transport.extra_attributes(), dict)
    assert isinstance(transport.default_config, TransportConfig)
    assert isinstance(transport.targets, Target)
    attrs = transport.attributes()
    assert attrs[ATTR_NAME] == transport_type.name
    assert isinstance(attrs[CONF_ENABLED], bool)
    assert attrs[CONF_DELIVERY_DEFAULTS] == transport.delivery_defaults
    assert isinstance(transport.build_standard_deliveries(mock_hass_api), dict)


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
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
    uut.record_error("test error msg", "test_method")
    attrs = uut.attributes()
    assert attrs["last_error_message"] == "test error msg"
    assert attrs["last_error_in"] == "test_method"
    assert attrs["error_count"] == 1


async def test_set_action_data(mock_hass: HomeAssistant) -> None:
    # Lines 122-124: set_action_data adds key when data is not None
    ctx = TestingContext(homeassistant=mock_hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
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
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
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
