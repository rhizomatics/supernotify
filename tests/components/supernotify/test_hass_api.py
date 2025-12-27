import socket
from typing import TYPE_CHECKING

import pytest
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables

from .hass_setup_lib import register_device

if TYPE_CHECKING:
    from custom_components.supernotify import ConditionsFunc


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

    devices = hass_api.discover_devices("testing", device_model_include=["Uni.*"])
    assert len(devices) == 1
    assert devices[0].identifiers == {("testing", "test_02")}

    devices = hass_api.discover_devices("testing", device_model_exclude=["Uni.*"])
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


def test_finds_service(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    def service_call(call: ServiceCall) -> ServiceResponse | None:
        return {}

    hass.services.async_register(domain="foo", service="bar", service_func=service_call)
    hass.services.async_register(domain="foo", service="xxx", service_func=service_call)

    assert hass_api.find_service("foo") == "bar"
    assert hass_api.find_service("bar") is None


async def test_mqtt_publish(mock_hass) -> None:
    hass_api = HomeAssistantAPI(mock_hass)
    hass_api.initialize()
    await hass_api.mqtt_publish("test.topic", {"foo": 123})
    mock_hass.data["mqtt"].client.async_publish.assert_called_once_with("test.topic", '{"foo":123}', 0, False)


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
