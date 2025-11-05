from dataclasses import asdict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition
from homeassistant.helpers import config_validation as cv

from custom_components.supernotify import PRIORITY_CRITICAL, PRIORITY_LOW, PRIORITY_MEDIUM
from custom_components.supernotify.model import ConditionVariables

""" test bed for checking conditions rather than supernotify functionality """


async def test_and_condition(hass: HomeAssistant) -> None:
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
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    cvars = ConditionVariables(["scenario-no-danger", "sunny"], [], [], PRIORITY_CRITICAL, {})

    hass.states.async_set("alarm_control_panel.home_alarm_control", "disarmed")
    assert not test(hass, asdict(cvars))

    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")
    assert test(hass, asdict(cvars))

    cvars.notification_priority = PRIORITY_LOW
    assert not test(hass, asdict(cvars))


async def test_template_condition(hass: HomeAssistant) -> None:
    """Test templated conditions."""
    config = {
        "condition": "template",
        "value_template": """
                        {% set n = states('sensor.bedroom_temperature') | float %}
                        {{ 15 <= n <= 20 }}""",
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)
    cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, {})

    hass.states.async_set("sensor.bedroom_temperature", "12")
    assert not test(hass, asdict(cvars))
    hass.states.async_set("sensor.bedroom_temperature", "21")
    assert not test(hass, asdict(cvars))
    hass.states.async_set("sensor.bedroom_temperature", "18")
    assert test(hass, asdict(cvars))
