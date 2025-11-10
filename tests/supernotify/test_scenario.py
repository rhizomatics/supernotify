import logging

from homeassistant.const import CONF_ALIAS, CONF_CONDITION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity
from pytest_unordered import unordered

from custom_components.supernotify import (
    ATTR_PRIORITY,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    CONF_SELECTION,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
    SCENARIO_SCHEMA,
    SELECTION_BY_SCENARIO,
)
from custom_components.supernotify import SUPERNOTIFY_SCHEMA as PLATFORM_SCHEMA
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.scenario import Scenario, ScenarioRegistry
from custom_components.supernotify.transports.generic import GenericTransport

_LOGGER = logging.getLogger(__name__)


async def test_simple_create(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario("testing", {}, mock_hass_api)
    assert await uut.validate()
    assert not uut.default
    assert await uut.validate()
    assert not await uut.evaluate()


async def test_simple_trace(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario("testing", {}, mock_hass_api)
    assert await uut.validate()
    assert not uut.default
    assert await uut.validate()
    assert not await uut.trace()


async def test_validate(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario(
        "testing", {"delivery": {"good": {}, "bad": {}, "ok": {}}, "action_groups": ["lights", "snoozes"]}, mock_hass_api
    )
    await uut.validate(valid_deliveries=["good", "ok"], valid_action_groups=["snoozes"])
    assert "bad" not in uut.delivery
    assert "good" in uut.delivery
    assert "ok" in uut.delivery
    assert "lights" not in uut.action_groups
    assert "snoozes" in uut.action_groups

    mock_hass_api.raise_issue.assert_called_with(  # type: ignore
        "scenario_testing_action_group_lights",
        is_fixable=False,
        issue_key="scenario_delivery",
        issue_map={"scenario": "testing", "action_group": "lights"},
        learn_more_url="https://supernotify.rhizomatics.github.io/#scenarios",
        severity=IssueSeverity.WARNING,
    )


async def test_conditional_create(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_ALIAS: "test001",
            CONF_CONDITION: {
                "condition": "and",
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "alarm_control_panel.home_alarm_control",
                        "state": ["armed_home", "armed_away"],
                    },
                    {
                        "condition": "template",
                        "value_template": "{{notification_priority in ['critical']}}",
                    },
                ],
            },
        }),
        hass_api,
    )
    assert await uut.validate()
    assert not uut.default
    assert await uut.validate()
    assert not await uut.evaluate(ConditionVariables([], [], [], PRIORITY_MEDIUM, {}))

    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")

    assert await uut.evaluate(ConditionVariables([], [], [], PRIORITY_CRITICAL, {}))


async def test_select_scenarios(hass: HomeAssistant, mock_context: Context) -> None:
    hass_api = HomeAssistantAPI(hass)
    config = PLATFORM_SCHEMA({
        "platform": "supernotify",
        "scenarios": {
            "select_only": {},
            "cold_day": {
                "alias": "Its a cold day",
                "condition": {
                    "condition": "template",
                    "value_template": """
                            {% set n = states('sensor.outside_temperature') | float %}
                            {{ n <= 10 }}""",
                },
            },
            "hot_day": {
                "alias": "Its a very hot day",
                "condition": {
                    "condition": "template",
                    "value_template": """
                                    {% set n = states('sensor.outside_temperature') | float %}
                                    {{ 30 <= n }}""",
                },
            },
        },
    })
    reg = ScenarioRegistry(config["scenarios"])
    hass.states.async_set("sensor.outside_temperature", "15")
    await reg.initialize({}, [], {}, hass_api)
    assert len(reg.scenarios) == 3
    mock_context.scenario_registry = reg
    uut = Notification(mock_context)
    await uut.initialize()
    hass.states.async_set("sensor.outside_temperature", "42")
    enabled = await uut.select_scenarios()
    assert enabled == ["hot_day"]

    hass.states.async_set("sensor.outside_temperature", "5")
    enabled = await uut.select_scenarios()
    assert enabled == ["cold_day"]

    hass.states.async_set("sensor.outside_temperature", "15")
    enabled = await uut.select_scenarios()
    assert enabled == []


async def test_scenario_templating(hass: HomeAssistant, uninitialized_unmocked_config: Context) -> None:
    hass_api = HomeAssistantAPI(hass)
    config = PLATFORM_SCHEMA({
        "platform": "supernotify",
        "scenarios": {
            "softly_softly": {
                "alias": "Gentle notification",
                "delivery": {
                    "alexa": {
                        "data": {
                            "message_template": '<amazon:effect name="whispered">{{notification_message}}</amazon:effect>',
                            "title_template": "",
                        }
                    }
                },
            },
            "emotional": {
                "alias": "emotional",
                "delivery": {
                    "alexa": {
                        "data": {
                            "message_template": '<amazon:emotion name="excited" intensity="medium">{{notification_message}}</amazon:emotion>'  # noqa: E501
                        }
                    }
                },
            },
        },
    })
    reg = ScenarioRegistry(config["scenarios"])
    context = uninitialized_unmocked_config
    # relies on a real hass Template class
    hass_api = HomeAssistantAPI(hass)
    context.hass_api = hass_api

    context.delivery_registry._deliveries = {"smtp": {CONF_TRANSPORT: "email"}, "alexa": {CONF_TRANSPORT: "alexa_devices"}}
    context.delivery_registry._transport_types = TRANSPORTS
    await context.delivery_registry.initialize(context)
    await reg.initialize(context.delivery_registry.deliveries, [], {}, hass_api)
    context.scenario_registry = reg
    uut = Notification(
        context,
        message="Hello from Home",
        title="Home Notification",
        action_data={"apply_scenarios": ["softly_softly"]},
    )
    await uut.initialize()
    assert uut.message("smtp") == "Hello from Home"
    assert uut.title("smtp") == "Home Notification"
    assert uut.message("alexa") == '<amazon:effect name="whispered">Hello from Home</amazon:effect>'
    assert uut.title("alexa") == ""

    uut = Notification(context, message="Please Sir", action_data={"apply_scenarios": ["softly_softly", "emotional"]})
    await uut.initialize()
    assert uut.message("smtp") == "Please Sir"
    assert (
        uut.message("alexa")
        == '<amazon:emotion name="excited" intensity="medium"><amazon:effect name="whispered">Please Sir</amazon:effect></amazon:emotion>'  # noqa: E501
    )

    uut = Notification(context, message="Please Sir", action_data={"apply_scenarios": ["emotional", "softly_softly"]})
    await uut.initialize()
    assert (
        uut.message("alexa")
        == '<amazon:effect name="whispered"><amazon:emotion name="excited" intensity="medium">Please Sir</amazon:emotion></amazon:effect>'  # noqa: E501
    )


async def test_scenario_constraint(hass: HomeAssistant, mock_context: Context) -> None:
    hass_api = HomeAssistantAPI(hass)
    mock_context.scenario_registry.delivery_by_scenario = {
        "Mostly": ["siren"],
        "Alarm": ["chime"],
    }

    mock_context.delivery_registry.implicit_deliveries = [  # type: ignore
        mock_context.delivery_registry.deliveries["plain_email"],
        mock_context.delivery_registry.deliveries["mobile"],
    ]
    mock_context.delivery_registry.deliveries["siren"] = Delivery("siren", {}, GenericTransport(mock_context))
    mock_context.scenario_registry.scenarios = {
        "Alarm": Scenario("Alarm", {}, hass_api),
        "Mostly": Scenario(
            "Mostly",
            SCENARIO_SCHEMA({
                CONF_ALIAS: "test001",
                CONF_CONDITION: {
                    "condition": "and",
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": "{{notification_priority not in ['critical']}}",
                        },
                    ],
                },
            }),
            hass_api,
        ),
    }
    uut = Notification(mock_context, "testing 123", action_data={ATTR_SCENARIOS_APPLY: ["Alarm"]})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime", "siren")
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={ATTR_SCENARIOS_CONSTRAIN: ["NULL"], ATTR_SCENARIOS_APPLY: ["Alarm"]},
    )
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")


async def test_scenario_suppress(hass: HomeAssistant, mock_context: Context) -> None:
    hass_api = HomeAssistantAPI(hass)
    mock_context.scenario_registry.delivery_by_scenario = {
        "Mostly": ["siren"],
        "Alarm": ["chime"],
        "DevNull": [],
    }
    mock_context.delivery_registry.deliveries["siren"] = Delivery(
        "siren", {CONF_SELECTION: [SELECTION_BY_SCENARIO]}, GenericTransport(mock_context)
    )
    mock_context.delivery_registry.deliveries["plain_email"].selection = [SELECTION_BY_SCENARIO]
    mock_context.delivery_registry.deliveries["chime"].selection = [SELECTION_BY_SCENARIO]
    mock_context.delivery_registry.deliveries["mobile"].selection = [SELECTION_BY_SCENARIO]

    mock_context.scenario_registry.scenarios = {
        "Alarm": Scenario("Alarm", {}, hass_api),
        "DevNull": Scenario("DevNull", {}, hass_api),
        "Mostly": Scenario(
            "Mostly",
            SCENARIO_SCHEMA({
                CONF_ALIAS: "test001",
                CONF_CONDITION: {
                    "condition": "and",
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": "{{notification_priority not in ['critical']}}",
                        },
                    ],
                },
            }),
            hass_api,
        ),
    }
    # Only deliveries for enabled scenarios
    uut = Notification(mock_context, "testing 123", action_data={ATTR_SCENARIOS_APPLY: ["Alarm"]})
    await uut.initialize()
    assert uut.applied_scenario_names == ["Alarm"]
    assert uut.selected_scenario_names == ["Mostly"]
    assert uut.selected_delivery_names == unordered("chime", "siren")

    # No selected scenarios
    uut = Notification(mock_context, "testing 123", action_data={ATTR_PRIORITY: PRIORITY_CRITICAL})
    await uut.initialize()
    assert uut.applied_scenario_names == []
    assert uut.selected_scenario_names == []
    assert uut.selected_delivery_names == []

    # Single scenario with no deliveries
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={ATTR_SCENARIOS_APPLY: ["DevNull"], ATTR_SCENARIOS_CONSTRAIN: ["DevNull"]},
    )
    await uut.initialize()
    assert uut.applied_scenario_names == ["DevNull"]
    assert list(uut.enabled_scenarios.keys()) == ["DevNull"]
    assert uut.selected_delivery_names == []


async def test_attributes(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            "delivery_selection": "implicit",
            "media": {"camera_entity_id": "camera.doorbell"},
            "delivery": {"doorbell_chime_alexa": {"data": {"amazon_magic_id": "a77464"}}, "email": {}},
            "condition": {
                "condition": "and",
                "conditions": [
                    {
                        "condition": "not",
                        "conditions": [
                            {
                                "condition": "state",
                                "enabled": True,
                                "entity_id": "alarm_control_panel.home_alarm_control",
                                "state": "disarmed",
                            }
                        ],
                    },
                    {"condition": "time", "after": "21:30:00", "before": "06:30:00"},
                ],
            },
        }),
        hass_api,
    )
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")
    assert await uut.validate()
    attrs = uut.attributes()
    assert attrs["delivery_selection"] == "implicit"

    assert attrs["delivery"]["doorbell_chime_alexa"]["data"]["amazon_magic_id"] == "a77464"


async def test_secondary_scenario(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITION: {"condition": "template", "value_template": '{{"scenario-possible-danger" in applied_scenarios}}'}
        }),
        hass_api,
    )
    assert await uut.validate()
    cvars = ConditionVariables(["scenario-no-danger", "sunny"], [], [], PRIORITY_MEDIUM, {})
    assert not uut.default
    assert await uut.validate()
    assert not await uut.evaluate(cvars)
    cvars.applied_scenarios.append("scenario-possible-danger")
    assert await uut.evaluate(cvars)


async def test_scenario_unknown_var(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITION: {
                "condition": "template",
                "value_template": '{{weather == "sunny" and "danger" in applied_scenarios}}',
            }
        }),
        hass_api,
    )
    assert not await uut.validate()


async def test_scenario_complex_hass_entities(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    hass.states.async_set("sensor.issues", "23")
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITION: {
                "condition": "or",
                "alias": "test complicated logic",
                "conditions": [
                    {
                        "condition": "and",
                        "conditions": [
                            # impossible AND, for test stability
                            {"condition": "sun", "after": "sunset", "before": "sunrise"},
                            {"condition": "sun", "before": "sunset", "after": "sunrise"},
                        ],
                    },
                    {
                        "condition": "not",
                        "conditions": [{"condition": "state", "entity_id": "sensor.issues", "state": "24"}],
                    },
                ],
            }
        }),
        hass_api,
    )
    assert await uut.validate()
    assert await uut.evaluate(ConditionVariables())
    hass.states.async_set("sensor.issues", "24")
    assert not await uut.evaluate(ConditionVariables())


async def test_scenario_shortcut_style(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({CONF_CONDITION: "{{ (state_attr('device_tracker.iphone', 'battery_level')|int) > 50 }}"}),
        hass_api,
    )
    hass.states.async_set("device_tracker.iphone", "on", attributes={"battery_level": 12})
    assert await uut.validate()
    assert not await uut.evaluate(ConditionVariables())
    hass.states.async_set("device_tracker.iphone", "on", attributes={"battery_level": 60})
    assert await uut.evaluate(ConditionVariables())


async def test_trace(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITION: {"condition": "template", "value_template": "{{'scenario-alert' in applied_scenarios}}"}
        }),
        hass_api,
    )
    assert await uut.validate()
    assert not uut.default
    assert await uut.trace(ConditionVariables(["scenario-alert"], [], [], PRIORITY_MEDIUM, {"AT_HOME": [{"name": "bob"}]}))
    assert uut.last_trace is not None
    _LOGGER.info("trace: %s", uut.last_trace.as_dict())
