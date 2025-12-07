from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify import PRIORITY_CRITICAL, PRIORITY_LOW, PRIORITY_MEDIUM, ConditionsFunc
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables

""" test bed for checking conditions rather than supernotify functionality """


async def test_and_conditions(hass: HomeAssistant) -> None:
    """Test the 'and' condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "state",
                "entity_id": "alarm_control_panel.home_alarm_control",
                "state": ["armed_home", "armed_away"],
            },
            {"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"},
        ],
    }
    config = cv.CONDITIONS_SCHEMA(config)
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    func: ConditionsFunc | None = await hass_api.build_conditions(config, True, True)
    assert func is not None

    cvars = ConditionVariables(["scenario-no-danger", "sunny"], [], [], PRIORITY_CRITICAL, {})

    hass.states.async_set("alarm_control_panel.home_alarm_control", "disarmed")
    assert not hass_api.evaluate_conditions(func, cvars)

    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")
    assert hass_api.evaluate_conditions(func, cvars)

    cvars.notification_priority = PRIORITY_LOW
    assert not hass_api.evaluate_conditions(func, cvars)


async def test_template_conditions(hass: HomeAssistant) -> None:
    """Test templated conditions."""
    config = {
        "condition": "template",
        "value_template": """
                        {% set n = states('sensor.bedroom_temperature') | float %}
                        {{ 15 <= n <= 20 }}""",
    }
    hass.states.async_set("sensor.bedroom_temperature", "0")
    config = cv.CONDITIONS_SCHEMA(config)
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    func: ConditionsFunc | None = await hass_api.build_conditions(config, True, True)
    assert func is not None

    cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, {})

    hass.states.async_set("sensor.bedroom_temperature", "12")
    assert not hass_api.evaluate_conditions(func, cvars)
    hass.states.async_set("sensor.bedroom_temperature", "21")

    assert not hass_api.evaluate_conditions(func, cvars)
    hass.states.async_set("sensor.bedroom_temperature", "18")
    assert hass_api.evaluate_conditions(func, cvars)
