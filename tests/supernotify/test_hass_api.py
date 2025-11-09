import socket

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify.hass_api import HomeAssistantAPI


def test_basic_setup(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    hass_api.initialize()
    assert hass_api.hass_name == "test home"
    assert hass_api.internal_url == f"http://{socket.gethostname()}"
    assert hass_api.external_url == hass_api.internal_url


async def test_evaluate_with_bad_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITION_SCHEMA({"condition": "xor"})
    with pytest.raises(HomeAssistantError):
        assert await hass_api.evaluate_condition(condition) is None


async def test_evaluates_good_true_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITION_SCHEMA({
        "condition": "template",
        "value_template": """
                        {% set n = "19.12" | float %}
                        {{ 15 <= n <= 20 }}""",
    })
    assert await hass_api.evaluate_condition(condition) is True


async def test_evaluates_good_false_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITION_SCHEMA({
        "condition": "template",
        "value_template": """
                        {% set n = "23.12" | float %}
                        {{ 15 <= n <= 20 }}""",
    })
    assert await hass_api.evaluate_condition(condition) is False


async def test_evaluates_ignores_missing_vars(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITION_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    assert await hass_api.evaluate_condition(condition) is False


async def test_evaluates_detects_missing_vars(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITION_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    with pytest.raises(HomeAssistantError):
        assert await hass_api.evaluate_condition(condition, strict=True) is False


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


async def test_async_roundtrips_entity_state(hass: HomeAssistant) -> None:
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
