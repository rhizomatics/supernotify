from __future__ import annotations

import logging
import socket
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import (
    ConditionErrorContainer,
    ConditionErrorMessage,
    HomeAssistantError,
    IntegrationError,
    ServiceNotFound,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component

from custom_components.supernotify.hass_api import (
    ATTR_APP_VERSION,
    ATTR_OS_NAME,
    ATTR_OS_VERSION,
    CONF_USER_ID,
    ConditionErrorLoggingAdaptor,
    HomeAssistantAPI,
    force_strict_template_mode,
)
from custom_components.supernotify.model import ConditionVariables, SelectionRule
from tests.components.supernotify.hass_setup_lib import TestingContext

from .hass_setup_lib import register_device, register_mobile_app

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

    from custom_components.supernotify.schema import ConditionsFunc


def test_abs_url(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    hass_api.initialize()
    hass_api.internal_url = "http://localhost:8123"
    hass_api.external_url = "https://testy001.nabucase.org"
    assert hass_api.abs_url("home", prefer_external=False) == "http://localhost:8123/home"
    assert hass_api.abs_url("/foo/home", prefer_external=False) == "http://localhost:8123/foo/home"
    assert hass_api.abs_url("home") == "https://testy001.nabucase.org/home"
    assert hass_api.abs_url("http:/11.5.6.3/me") == "http:/11.5.6.3/me"


def test_basic_setup(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    hass_api.initialize()
    assert hass_api.hass_name == "test home"
    assert hass_api.internal_url == f"http://{socket.gethostname()}"
    assert hass_api.external_url == hass_api.internal_url


async def test_evaluate_with_bad_conditions(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITIONS_SCHEMA({"condition": "xor"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_conditions(condition)


async def test_evaluates_good_true_conditions(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {% set n = "19.12" | float %}
                        {{ 15 <= n <= 20 }}""",
    })
    checker: ConditionsFunc | None = await hass_api.build_conditions(condition)
    assert checker
    assert hass_api.evaluate_conditions(checker, ConditionVariables()) is True


async def test_evaluates_good_false_conditions(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {% set n = "23.12" | float %}
                        {{ 15 <= n <= 20 }}""",
    })
    checker: ConditionsFunc | None = await hass_api.build_conditions(condition)
    assert checker
    assert hass_api.evaluate_conditions(checker, ConditionVariables()) is False


@pytest.mark.parametrize(argnames="validate", argvalues=[True, False], ids=["validated", "unvalidated"])
async def test_unstrict_evaluates_ignores_missing_vars(hass: HomeAssistant, validate: bool) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    checker: ConditionsFunc | None = await hass_api.build_conditions(condition, validate=validate)
    assert checker
    assert hass_api.evaluate_conditions(checker, ConditionVariables()) is False


@pytest.mark.parametrize(argnames="validate", argvalues=[True, False], ids=["validated", "unvalidated"])
async def test_strict_evaluates_detects_missing_vars(hass: HomeAssistant, validate: bool) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ xotification_priority == 'critical' }}"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_conditions(condition, validate=validate, strict=True)


@pytest.mark.parametrize(argnames="validate", argvalues=[True, False], ids=["validated", "unvalidated"])
@pytest.mark.parametrize(argnames="strict", argvalues=[True, False], ids=["strict", "lax"])
async def test_evaluates_respects_conditionvars(hass: HomeAssistant, validate: bool, strict: bool) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": "{{ notification_priority != 'no_such_value' }}",
    })
    checker: ConditionsFunc | None = await hass_api.build_conditions(condition, validate=validate, strict=strict)
    assert checker
    assert hass_api.evaluate_conditions(checker, ConditionVariables())


def test_roundtrips_entity_state(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    assert hass_api.get_state("entity.testablity") is None
    hass_api.set_state("entity.testablity", "on")
    state = hass_api.get_state("entity.testablity")
    assert state is not None
    assert state.state == "on"

    hass_api.set_state("entity.testablity", "off")
    state = hass_api.get_state("entity.testablity")
    assert state is not None
    assert state.state == "off"


def test_async_roundtrips_entity_state(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    assert hass_api.get_state("entity.testablity") is None
    hass_api.set_state("entity.testablity", "on")
    state = hass_api.get_state("entity.testablity")
    assert state is not None
    assert state.state == "on"

    hass_api.set_state("entity.testablity", "off")
    state = hass_api.get_state("entity.testablity")
    assert state is not None
    assert state.state == "off"


def test_discover_devices_finds_nothing(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    assert hass_api.discover_devices("nosuchdomain") == []


def test_discover_devices_finds_only_devices_for_domain(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    register_device(
        hass_api, device_id="00001111222233334444555566667777", domain="unit_testing", domain_id="test_01", title="test fixture"
    )
    register_device(
        hass_api,
        device_id="10001111222233334444555566667777",
        domain="unit_testing",
        domain_id="test_02",
        title="2nd test fixture",
    )
    register_device(
        hass_api,
        device_id="20001111222233334444555566667777",
        domain="integration_testing",
        domain_id="itest_01",
        title="integration test fixture",
    )
    register_device(
        hass_api,
        device_id="10001111222233334444555566667777",
        domain="unit_testing",
        domain_id="test_02",
        identifiers={("unit_testing", "weird", "triple_identifier")},
    )
    register_device(
        hass_api,
        device_id="10001111222233334444555566667777",
        domain="unit_testing",
        domain_id="test_02",
        title="Broken device",
        identifiers={("unit_testing",)},
    )

    devices = hass_api.discover_devices("unit_testing")
    assert len(devices) == 3
    assert devices[0].identifiers == {("unit_testing", "test_01")}
    assert devices[1].identifiers == {("unit_testing", "test_02")}
    assert devices[2].identifiers == {("unit_testing", "weird", "triple_identifier")}  # type: ignore


def test_discover_devices_filters_models(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    register_device(
        hass_api, device_id="00001111222233334444555566667777", domain="testing", domain_id="test_01", title="test fixture"
    )
    register_device(
        hass_api,
        device_id="10001111222233334444555566667777",
        domain="testing",
        domain_id="test_02",
        model="Unit",
        title="2nd test fixture",
    )
    register_device(
        hass_api,
        device_id="20001111222233334444555566667777",
        domain="testing",
        domain_id="test_03",
        model="Integration",
        title="2nd test fixture",
    )

    devices = hass_api.discover_devices("testing", device_model_select=SelectionRule(["Uni.*"]))
    assert len(devices) == 1
    assert devices[0].identifiers == {("testing", "test_02")}

    devices = hass_api.discover_devices("testing", device_model_select=SelectionRule({"exclude": ["Uni.*"]}))
    assert len(devices) == 2
    assert devices[0].identifiers == {("testing", "test_01")}
    assert devices[1].identifiers == {("testing", "test_03")}


def test_hass_doesnt_have_weird_service(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    assert not hass_api.has_service("nosuchdomain", "nosuchservice")


async def test_hass_calls_service_fire_and_forget(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    with pytest.raises(ServiceNotFound):
        assert await hass_api.call_service("nosuchdomain", "nosuchservice") is None


async def test_call_service_propagates_context(hass: HomeAssistant) -> None:
    """The calling HA Context, when supplied, should reach the underlying service call
    so the logbook/trace can chain the resulting action back to its trigger."""
    from homeassistant.core import Context

    hass_api = HomeAssistantAPI(hass)
    seen_contexts: list[Context | None] = []

    async def service_call(call: ServiceCall) -> None:
        seen_contexts.append(call.context)

    hass.services.async_register("testing", "context_probe", service_call)

    caller_context = Context()
    await hass_api.call_service("testing", "context_probe", context=caller_context, blocking=True)

    assert seen_contexts == [caller_context]


def test_finds_service(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    def service_call(call: ServiceCall) -> ServiceResponse | None:
        return {}

    class TestingService:
        async def service_call(self, call: ServiceCall) -> ServiceResponse | None:
            return {}

    hass.services.async_register(domain="foo", service="bar", service_func=service_call)
    hass.services.async_register(domain="foo", service="xxx", service_func=service_call)
    hass.services.async_register(domain="foo2", service="clz", service_func=TestingService.service_call)  # type: ignore

    assert hass_api.find_service("bar", "supernotify.test_hass_api") is None
    assert hass_api.find_service("foo", "supernotify.test_hass_api") == "foo.bar"
    assert hass_api.find_service("foo2", "supernotify.test_hass_api") == "foo2.clz"


async def test_coerce_schema_does_nothing_for_unknown_service(hass) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    data = {"m": 123, "data": {"bob": "joe"}}
    assert ctx.hass_api.coerce_schema("foo", "bar", data) == data


async def test_coerce_schema_cleans_up_notify_entity_action(hass) -> None:
    ctx = TestingContext(homeassistant=hass)
    assert await async_setup_component(hass, "notify", {})
    await hass.async_block_till_done()
    await ctx.test_initialize()

    data = {"message": 123, "data": {"bob": "joe"}, "funky": True}
    cleaned = ctx.hass_api.coerce_schema("notify", "send_message", data)
    assert cleaned["message"] == "123"
    assert "data" not in cleaned
    assert "funky" not in cleaned


async def test_coerce_schema_cleans_up_legacy_action(hass) -> None:
    ctx = TestingContext(homeassistant=hass)
    config = {"notify_events": {"token": "ABC"}, "notify": [{"name": "eventer", "platform": "notify_events"}]}
    assert await async_setup_component(hass, "notify_events", config)

    await hass.async_block_till_done()
    await ctx.test_initialize()

    data = {"message": 123, "data": {"bob": "joe"}, "funky": True}
    cleaned = ctx.hass_api.coerce_schema("notify", "eventer", data)
    assert cleaned["message"] == "123"
    assert cleaned["data"] == {"bob": "joe"}
    assert "funky" not in cleaned


async def test_coerce_schema_cleans_up_non_notify_action(hass) -> None:
    ctx = TestingContext(homeassistant=hass)
    assert await async_setup_component(hass, "siren", {"siren": {"platform": "demo"}})
    await hass.async_block_till_done()
    await ctx.test_initialize()

    data = {"duration": 1.0, "foo": 123, "funky": True}
    cleaned = ctx.hass_api.coerce_schema("siren", "turn_on", data)
    assert cleaned["duration"] == pytest.approx(1.0, rel=0.01)
    assert "funky" not in cleaned
    assert "foo" not in cleaned


async def test_mqtt_publish(mock_hass) -> None:
    hass_api = HomeAssistantAPI(mock_hass)
    hass_api.initialize()
    await hass_api.mqtt_publish("test.topic", {"foo": 123})
    # older HA versions don't pass message_expiry_interval to client.async_publish at all
    call = mock_hass.data["mqtt"].client.async_publish.call_args
    assert call.args == ("test.topic", '{"foo":123}', 0, False)
    assert call.kwargs.get("message_expiry_interval") is None


async def test_subscribe_and_unsubscribe(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    calls: int = 0

    def listener(*args, **kwargs):
        nonlocal calls
        calls += 1

    hass_api.subscribe_event("wonders_of_core", listener)
    hass.bus.async_fire("wonders_of_core", {})
    await hass.async_block_till_done()  # type: ignore
    assert calls == 1

    assert hass_api.unsubscribes[0].args[0] == "wonders_of_core"  # type: ignore

    hass_api.disconnect()
    assert not hass_api.unsubscribes
    hass.bus.async_fire("wonders_of_core", {})
    await hass.async_block_till_done()
    assert calls == 1


def test_device_info_equality() -> None:
    from custom_components.supernotify.hass_api import DeviceInfo

    d1 = DeviceInfo(device_id="abc", device_name="My Device")
    d2 = DeviceInfo(device_id="abc", device_name="My Device")
    d3 = DeviceInfo(device_id="xyz", device_name="Other")
    assert d1 == d2
    assert d1 != d3
    assert d1 != None  # noqa: RUF100, E711


def test_disconnect_handles_unsubscribe_error(hass: HomeAssistant) -> None:
    # Lines 159-160: error during unsubscribe is caught and logged
    hass_api = HomeAssistantAPI(hass)

    def bad_unsub() -> None:
        raise RuntimeError("unsub failed")

    hass_api.unsubscribes.append(bad_unsub)  # type: ignore[arg-type]
    hass_api.disconnect()  # should not raise
    assert hass_api.unsubscribes == []


def test_raise_issue(mock_hass: HomeAssistant) -> None:
    # Line 392: raise_issue calls ir.async_create_issue
    hass_api = HomeAssistantAPI(mock_hass)
    hass_api.initialize()
    # Should not raise even with mock hass
    hass_api.raise_issue("test_issue", "test_key", {"key": "value"})


def test_build_mobile_app_cache_no_entity_registry(mock_hass: HomeAssistant) -> None:
    # Lines 407-408: logs warning when entity registry unavailable
    from unittest.mock import patch

    hass_api = HomeAssistantAPI(mock_hass)
    with patch.object(hass_api, "entity_registry", return_value=None):
        hass_api.build_mobile_app_cache()  # should not raise


def test_discover_devices_skips_disabled(hass: HomeAssistant) -> None:
    # Line 477: disabled devices are skipped
    from homeassistant.helpers.device_registry import DeviceEntryDisabler

    hass_api = HomeAssistantAPI(hass)
    dev_entry = register_device(hass_api, domain="test_disabled", domain_id="dd_01")
    dev_reg = hass_api.device_registry()
    if dev_entry and dev_reg:
        dev_reg.async_update_device(dev_entry.id, disabled_by=DeviceEntryDisabler.USER)
    devices = hass_api.discover_devices("test_disabled")
    assert len(devices) == 0


def test_is_state(hass: HomeAssistant) -> None:
    # Line 178
    hass_api = HomeAssistantAPI(hass)
    hass_api.set_state("entity.is_state_test", "on")
    assert hass_api.is_state("entity.is_state_test", "on")
    assert not hass_api.is_state("entity.is_state_test", "off")


async def test_fire_event(hass: HomeAssistant) -> None:
    # Line 201
    hass_api = HomeAssistantAPI(hass)
    calls: list[dict] = []
    hass.bus.async_listen("supernotify_test_fire_event", lambda event: calls.append(event.data))
    hass_api.fire_event("supernotify_test_fire_event", {"foo": "bar"})
    await hass.async_block_till_done()
    assert calls == [{"foo": "bar"}]


def test_mobile_app_by_tracker_unknown(hass: HomeAssistant) -> None:
    # Line 470
    hass_api = HomeAssistantAPI(hass)
    assert hass_api.mobile_app_by_tracker("device_tracker.nope") is None


def test_initialize_warns_on_invalid_internal_url(hass: HomeAssistant) -> None:
    # Line 150
    hass_api = HomeAssistantAPI(hass)
    with patch("custom_components.supernotify.hass_api.get_url", side_effect=["ftp://nope", "https://ext.example"]):
        hass_api.initialize()
    assert hass_api.internal_url == "ftp://nope"
    assert hass_api.external_url == "https://ext.example"


def test_find_config_entry_data_unavailable() -> None:
    # Line 330: hass_avail guard returns None when config_entries isn't present
    fake_hass = Mock()
    fake_hass.config_entries = None
    hass_api = HomeAssistantAPI(fake_hass)  # type: ignore[arg-type]
    assert hass_api.find_config_entry_data("foo") is None


async def test_coerce_schema_handles_unexpected_coercion_failure(hass: HomeAssistant) -> None:
    # Lines 283-285: any exception raised while coercing is caught and original data returned
    hass_api = HomeAssistantAPI(hass)
    hass_api._service_info[("foo", "bar")] = {"schema": vol.Schema({vol.Required("num"): int})}
    data = {"num": "not-an-int"}
    assert hass_api.coerce_schema("foo", "bar", data) == data


def test_service_info_handles_exception(mock_hass: HomeAssistant) -> None:
    # Lines 303-304
    hass_api = HomeAssistantAPI(mock_hass)
    mock_hass.services.async_services_for_domain.side_effect = RuntimeError("boom")
    assert hass_api.service_info("foo", "bar") == SupportsResponse.NONE


async def test_build_conditions_validate_failure_reraises(hass: HomeAssistant) -> None:
    # Lines 401-403
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ true }}"})
    with (
        patch(
            "custom_components.supernotify.hass_api.condition_helper.async_validate_conditions_config",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(RuntimeError),
    ):
        await hass_api.build_conditions(condition, validate=True)


async def test_build_conditions_raises_when_no_test_built(hass: HomeAssistant) -> None:
    # Line 412
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ true }}"})
    with (
        patch(
            "custom_components.supernotify.hass_api.condition_helper.async_conditions_from_config",
            AsyncMock(return_value=None),
        ),
        pytest.raises(IntegrationError),
    ):
        await hass_api.build_conditions(condition)


def test_evaluate_conditions_warns_on_missing_vars(hass: HomeAssistant) -> None:
    # Lines 433-434: warns and passes None through when condition_variables is None
    hass_api = HomeAssistantAPI(hass)
    assert hass_api.evaluate_conditions(lambda variables: variables is None, None) is True  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_evaluate_conditions_reraises_exception(hass: HomeAssistant) -> None:
    # Lines 435-437
    hass_api = HomeAssistantAPI(hass)

    def bad_conditions(variables: Mapping[str, Any] | None) -> bool:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        hass_api.evaluate_conditions(bad_conditions, ConditionVariables())


async def test_trace_conditions_propagates_exception(hass: HomeAssistant) -> None:
    # Lines 758-761: trace_action re-raises exceptions from the traced body
    hass_api = HomeAssistantAPI(hass)

    def bad_conditions(variables: Mapping[str, Any] | None) -> bool:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await hass_api.trace_conditions(bad_conditions, ConditionVariables())


def test_build_mobile_app_cache_warns_when_no_notify_service(hass: HomeAssistant) -> None:
    # Line 499: no matching notify.* service found for a discovered mobile_app device
    hass_api = HomeAssistantAPI(hass)
    register_device(
        hass_api,
        device_id="30001111222233334444555566667777",
        domain="mobile_app",
        domain_id="no_notify_service",
        title="No Notify Phone",
    )
    hass_api.build_mobile_app_cache()
    found = hass_api.mobile_app_by_id("mobile_app_no_notify_phone")
    assert found is not None
    assert found.action is None


def test_build_mobile_app_cache_handles_device_exception(hass: HomeAssistant) -> None:
    # Lines 522-523: a failure examining one device is logged, not raised
    hass_api = HomeAssistantAPI(hass)
    register_device(hass_api, device_id="40001111222233334444555566667777", domain="mobile_app", domain_id="broken_device")
    with patch.object(hass_api, "has_service", side_effect=RuntimeError("boom")):
        hass_api.build_mobile_app_cache()  # should not raise
    assert hass_api.mobile_app_by_device_id("40001111222233334444555566667777") is None


def test_device_config_info_falls_back_to_deprecated_config_entries(hass: HomeAssistant) -> None:
    # Lines 532-534: pre-2026.8 devices without config_entry_id fall back to config_entries
    hass_api = HomeAssistantAPI(hass)
    device = Mock(spec=["config_entries"])
    device.config_entries = ()
    result = hass_api.device_config_info(device)  # type: ignore[arg-type]
    assert result == {ATTR_OS_NAME: None, ATTR_OS_VERSION: None, CONF_USER_ID: None, ATTR_APP_VERSION: None}


def test_discover_devices_no_device_registry(hass: HomeAssistant) -> None:
    # Lines 554-555
    hass_api = HomeAssistantAPI(hass)
    with patch.object(hass_api, "device_registry", return_value=None):
        assert hass_api.discover_devices("mobile_app") == []


def test_discover_devices_filters_os_area_and_labels(hass: HomeAssistant) -> None:
    # Lines 579-583, 585-587, 589-591
    hass_api = HomeAssistantAPI(hass)
    register_mobile_app(hass_api, person="person.filter_test", device_name="filterphone", os_name="iOS")

    assert hass_api.discover_devices("mobile_app", device_os_select=SelectionRule(["Android"])) == []
    assert hass_api.discover_devices("mobile_app", device_area_select=SelectionRule(["kitchen"])) == []
    assert hass_api.discover_devices("mobile_app", device_label_select=SelectionRule(["urgent"])) == []


def test_discover_devices_logs_unexpected_device_without_id(hass: HomeAssistant) -> None:
    # Line 612
    hass_api = HomeAssistantAPI(hass)
    register_device(
        hass_api,
        device_id="60001111222233334444555566667777",
        domain="unit_testing",
        domain_id="empty_id",
        identifiers={()},
    )
    devices = hass_api.discover_devices("unit_testing")
    assert devices == []


def test_domain_for_device_no_match_returns_none(hass: HomeAssistant) -> None:
    # Lines 632-636
    hass_api = HomeAssistantAPI(hass)
    dev_entry = register_device(
        hass_api, device_id="50001111222233334444555566667777", domain="unit_testing", domain_id="dfd_01"
    )
    assert dev_entry is not None
    assert hass_api.domain_for_device(dev_entry.id, ["some_other_domain"]) is None


def test_entity_registry_handles_exception(hass: HomeAssistant) -> None:
    # Lines 646-647
    hass_api = HomeAssistantAPI(hass)
    with patch("custom_components.supernotify.hass_api.er.async_get", side_effect=RuntimeError("boom")):
        assert hass_api.entity_registry() is None


def test_device_registry_handles_exception(hass: HomeAssistant) -> None:
    # Lines 658-659
    hass_api = HomeAssistantAPI(hass)
    with patch("custom_components.supernotify.hass_api.dr.async_get", side_effect=RuntimeError("boom")):
        assert hass_api.device_registry() is None


async def test_mqtt_available_raises_by_default(mock_hass: HomeAssistant) -> None:
    # Lines 667-671
    hass_api = HomeAssistantAPI(mock_hass)
    with (
        patch("homeassistant.components.mqtt.async_wait_for_mqtt_client", AsyncMock(side_effect=RuntimeError("boom"))),
        pytest.raises(RuntimeError),
    ):
        await hass_api.mqtt_available()


async def test_mqtt_available_swallows_when_not_raising(mock_hass: HomeAssistant) -> None:
    # Lines 667-671
    hass_api = HomeAssistantAPI(mock_hass)
    with patch("homeassistant.components.mqtt.async_wait_for_mqtt_client", AsyncMock(side_effect=RuntimeError("boom"))):
        assert await hass_api.mqtt_available(raise_on_error=False) is False


async def test_mqtt_publish_raises_by_default(mock_hass: HomeAssistant) -> None:
    # Lines 686-689
    hass_api = HomeAssistantAPI(mock_hass)
    with (
        patch("homeassistant.components.mqtt.async_publish", AsyncMock(side_effect=RuntimeError("boom"))),
        pytest.raises(RuntimeError),
    ):
        await hass_api.mqtt_publish("test.topic", {"a": 1})


async def test_mqtt_publish_swallows_when_not_raising(mock_hass: HomeAssistant) -> None:
    # Lines 686-689
    hass_api = HomeAssistantAPI(mock_hass)
    with patch("homeassistant.components.mqtt.async_publish", AsyncMock(side_effect=RuntimeError("boom"))):
        await hass_api.mqtt_publish("test.topic", {"a": 1}, raise_on_error=False)  # should not raise


def test_condition_error_logging_adaptor_captures_errors() -> None:
    # Lines 703, 706-707: capture() collects ConditionError/ConditionErrorContainer instances
    # A mock logger is used because ConditionErrorLoggingAdaptor.error()/warning() pass args
    # as `self.logger.error(msg, args, kwargs)` rather than `self.logger.error(msg, *args, **kwargs)` -
    # a real logger's message formatting blows up on the resulting mismatched args (see report).
    mock_logger = Mock(spec=logging.Logger)
    adaptor = ConditionErrorLoggingAdaptor(mock_logger)
    err = ConditionErrorMessage(type="test", message="bad condition")
    adaptor.error("problem: %s", err)
    assert adaptor.condition_errors == [err]
    mock_logger.error.assert_called_once()

    container = ConditionErrorContainer("and", errors=[err])
    adaptor.warning("problem: %s", container)
    assert adaptor.condition_errors == [err, err]
    mock_logger.warning.assert_called_once()


def test_force_strict_template_mode_wraps_templates(hass: HomeAssistant) -> None:
    # Lines 722, 737: __getattr__ passthrough and recursion into nested dicts.
    tmpl = Template("{{ 1 }}", hass)
    nested_tmpl = Template("{{ 2 }}", hass)
    cond: dict[str, Any] = {"value_template": tmpl, "nested": {"value_template": nested_tmpl}}

    force_strict_template_mode([cond], undo=False)
    wrapped = cond["value_template"]
    assert wrapped.hass is hass  # __getattr__ passthrough, line 722
    nested_wrapped = cond["nested"]["value_template"]
    assert nested_wrapped.hass is hass  # recursion into nested dict, line 737


def test_force_strict_template_mode_undo_restores_original_template(hass: HomeAssistant) -> None:
    # Line 735: undo=True on a separate call must restore the original Template objects.
    tmpl = Template("{{ 1 }}", hass)
    cond: dict[str, Any] = {"value_template": tmpl}

    force_strict_template_mode([cond], undo=False)
    force_strict_template_mode([cond], undo=True)

    assert cond["value_template"] is tmpl
