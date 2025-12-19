import logging

from homeassistant.const import CONF_ACTION, CONF_ALIAS, CONF_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity
from pytest_unordered import unordered

from custom_components.supernotify import (
    ATTR_PRIORITY,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    CONF_DELIVERY,
    CONF_SELECTION,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
    SCENARIO_SCHEMA,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.scenario import Scenario

from .doubles_lib import DummyTransport
from .hass_setup_lib import TestingContext

_LOGGER = logging.getLogger(__name__)


async def test_simple_create(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario("testing", {}, mock_hass_api)
    assert await uut.validate()
    assert await uut.validate()
    assert not uut.evaluate(ConditionVariables())


async def test_simple_trace(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario("testing", {}, mock_hass_api)
    assert await uut.validate()
    assert await uut.validate()
    assert not await uut.trace(ConditionVariables())


async def test_validate(mock_hass_api: HomeAssistantAPI) -> None:
    uut = Scenario(
        "testing", {"delivery": {"good": {}, "bad": {}, "ok": {}}, "action_groups": ["lights", "snoozes"]}, mock_hass_api
    )
    await uut.validate(valid_delivery_names=["good", "ok"], valid_action_group_names=["snoozes"])
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
        learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
        severity=IssueSeverity.WARNING,
    )


async def test_conditional_create(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_ALIAS: "test001",
            CONF_CONDITIONS: {
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
    assert await uut.validate()
    assert not uut.evaluate(ConditionVariables([], [], [], PRIORITY_MEDIUM, {}))

    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")

    assert uut.evaluate(ConditionVariables([], [], [], PRIORITY_CRITICAL, {}))


async def test_select_scenarios(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        scenarios={
            "select_only": {},
            "cold_day": {
                "alias": "Its a cold day",
                "conditions": {
                    "condition": "template",
                    "value_template": """
                            {% set n = states('sensor.outside_temperature') | float %}
                            {{ n <= 10 }}""",
                },
            },
            "hot_day": {
                "alias": "Its a very hot day",
                "conditions": {
                    "condition": "template",
                    "value_template": """
                                    {% set n = states('sensor.outside_temperature') | float %}
                                    {{ 30 <= n }}""",
                },
            },
        },
    )
    # register entity first so template validates
    hass.states.async_set("sensor.outside_temperature", "20")
    await ctx.test_initialize()
    uut = Notification(ctx)
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


async def test_scenario_templating(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        scenarios={
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
        deliveries={"smtp": {CONF_TRANSPORT: "email", CONF_ACTION: "notify.smtp"}, "alexa": {CONF_TRANSPORT: "alexa_devices"}},
        transport_types=TRANSPORTS,
    )
    await ctx.test_initialize()

    notification = Notification(
        ctx,
        message="Hello from Home",
        title="Home Notification",
        action_data={"apply_scenarios": ["softly_softly"]},
    )
    await notification.initialize()

    smtp_envelope = Envelope(ctx.delivery("smtp"), notification, context=ctx)
    assert smtp_envelope._compute_message() == "Hello from Home"
    assert smtp_envelope._compute_title() == "Home Notification"
    alexa_envelope = Envelope(ctx.delivery("alexa"), notification, context=ctx)
    assert alexa_envelope._compute_message() == '<amazon:effect name="whispered">Hello from Home</amazon:effect>'
    assert alexa_envelope._compute_title() == ""

    notification = Notification(ctx, message="Please Sir", action_data={"apply_scenarios": ["softly_softly", "emotional"]})
    await notification.initialize()
    smtp_envelope = Envelope(ctx.delivery("smtp"), notification, context=ctx)
    assert smtp_envelope._compute_message() == "Please Sir"
    alexa_envelope = Envelope(ctx.delivery("alexa"), notification, context=ctx)
    assert (
        alexa_envelope._compute_message()
        == '<amazon:emotion name="excited" intensity="medium"><amazon:effect name="whispered">Please Sir</amazon:effect></amazon:emotion>'  # noqa: E501
    )

    notification = Notification(ctx, message="Please Sir", action_data={"apply_scenarios": ["emotional", "softly_softly"]})
    await notification.initialize()
    alexa_envelope = Envelope(ctx.delivery("alexa"), notification, context=ctx)
    assert (
        alexa_envelope._compute_message()
        == '<amazon:effect name="whispered"><amazon:emotion name="excited" intensity="medium">Please Sir</amazon:emotion></amazon:effect>'  # noqa: E501
    )


async def test_scenario_constraint(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        scenarios={
            "Alarm": {CONF_DELIVERY: {"chime": {}}},
            "Mostly": {
                CONF_ALIAS: "test001",
                CONF_DELIVERY: {"siren": {}},
                CONF_CONDITIONS: {
                    "condition": "and",
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": "{{notification_priority not in ['critical']}}",
                        },
                    ],
                },
            },
        },
        deliveries={
            "plain_email": {CONF_TRANSPORT: "dummy"},
            "mobile": {CONF_TRANSPORT: "dummy"},
            "siren": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
            "chime": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
        },
        transport_types=[DummyTransport],
    )

    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: ["Alarm"]})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime", "siren")
    uut = Notification(
        ctx,
        "testing 123",
        action_data={ATTR_SCENARIOS_CONSTRAIN: ["NULL"], ATTR_SCENARIOS_APPLY: ["Alarm"]},
    )
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")  # siren constrained


async def test_scenario_suppress(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "plain_email": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
            "mobile": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
            "siren": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
            "chime": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "scenario"},
        },
        transport_types=[DummyTransport],
        scenarios={
            "Alarm": {CONF_DELIVERY: {"chime": {}}},
            "No_Mobile": {CONF_DELIVERY: {"mobile": {"enabled": False}}},
            "DevNull": {},
            "Mostly": {
                CONF_ALIAS: "test001",
                CONF_DELIVERY: {"siren": {}},
                CONF_CONDITIONS: {
                    "condition": "and",
                    "conditions": [
                        {
                            "condition": "template",
                            "value_template": "{{notification_priority not in ['critical']}}",
                        },
                    ],
                },
            },
        },
    )
    await ctx.test_initialize()

    # Only deliveries for enabled scenarios
    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: ["Alarm"]})
    await uut.initialize()
    assert uut.applied_scenario_names == ["Alarm"]
    assert uut.selected_scenario_names == ["Mostly"]
    assert uut.selected_delivery_names == unordered("chime", "siren")

    # No selected scenarios
    uut = Notification(ctx, "testing 123", action_data={ATTR_PRIORITY: PRIORITY_CRITICAL})
    await uut.initialize()
    assert uut.applied_scenario_names == []
    assert uut.selected_scenario_names == []
    assert uut.selected_delivery_names == []

    # Single scenario with no deliveries
    uut = Notification(
        ctx,
        "testing 123",
        action_data={ATTR_SCENARIOS_APPLY: ["DevNull"], ATTR_SCENARIOS_CONSTRAIN: ["DevNull"]},
    )
    await uut.initialize()
    assert uut.applied_scenario_names == ["DevNull"]
    assert list(uut.enabled_scenarios.keys()) == ["DevNull"]
    assert uut.selected_delivery_names == []

    # Switch off one delivery
    uut = Notification(
        ctx,
        "testing 123",
        action_data={ATTR_SCENARIOS_APPLY: ["No_Mobile"], ATTR_SCENARIOS_CONSTRAIN: ["No_Mobile"]},
    )


async def test_scenario_selectively_disable_delivery(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "plain_email": {CONF_TRANSPORT: "dummy"},
            "mobile": {CONF_TRANSPORT: "dummy"},
            "siren": {CONF_TRANSPORT: "dummy"},
            "chime": {CONF_TRANSPORT: "dummy"},
        },
        transport_types=[DummyTransport],
        scenarios={"No_Mobile": {CONF_DELIVERY: {"mobile": {"enabled": False}}}},
    )
    await ctx.test_initialize()

    # Switch off one delivery
    uut = Notification(
        ctx,
        "testing 123",
        action_data={ATTR_SCENARIOS_APPLY: ["No_Mobile"], ATTR_SCENARIOS_CONSTRAIN: ["No_Mobile"]},
    )
    await uut.initialize()
    assert uut.applied_scenario_names == ["No_Mobile"]
    assert list(uut.enabled_scenarios.keys()) == ["No_Mobile"]
    assert uut.selected_delivery_names == unordered("plain_email", "siren", "chime")


async def test_scenario_selectively_override_delivery(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"plain_email": {CONF_TRANSPORT: "dummy"}, "sms": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
        scenarios={"Spammy": {CONF_DELIVERY: {"plain_email": {"data": {"priority": "low"}}}}},
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        target="abc123",
        action_data={ATTR_SCENARIOS_APPLY: ["Spammy"], ATTR_SCENARIOS_CONSTRAIN: ["Spammy"]},
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.applied_scenario_names == ["Spammy"]
    assert len(uut.delivered_envelopes["dummy"]) == 2
    emailed = next(e for e in uut.delivered_envelopes["dummy"] if e.delivery_name == "plain_email")
    texted = next(e for e in uut.delivered_envelopes["dummy"] if e.delivery_name == "sms")
    assert emailed.priority == "low"
    assert texted.priority == "medium"


async def test_scenario_override_only_preselected_delivery(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"plain_email": {CONF_TRANSPORT: "dummy", CONF_SELECTION: "explicit"}, "text": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
        scenarios={"Spammy": {CONF_DELIVERY: {"plain_email": {"enabled": None, "data": {"priority": "low"}}}}},
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        target="abc123",
        action_data={ATTR_SCENARIOS_APPLY: ["Spammy"], ATTR_SCENARIOS_CONSTRAIN: ["Spammy"]},
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.applied_scenario_names == ["Spammy"]
    assert len(uut.delivered_envelopes["dummy"]) == 1
    assert uut.delivered_envelopes["dummy"][0].delivery_name == "text"


async def test_scenario_supplied_target(hass: HomeAssistant) -> None:

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"plain_email": {CONF_TRANSPORT: "dummy"}, "sms": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
        scenarios={"Spammy": {CONF_DELIVERY: {"plain_email": {"target": ["spambox@myhome.org"]}}}},
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        target="abc123",
        action_data={ATTR_SCENARIOS_APPLY: ["Spammy"], ATTR_SCENARIOS_CONSTRAIN: ["Spammy"]},
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.applied_scenario_names == ["Spammy"]
    assert len(uut.delivered_envelopes["dummy"]) == 2
    emailed = next(e for e in uut.delivered_envelopes["dummy"] if e.delivery_name == "plain_email")
    texted = next(e for e in uut.delivered_envelopes["dummy"] if e.delivery_name == "sms")
    assert "spambox@myhome.org" in emailed.target.email
    assert "spambox@myhome.org" not in texted.target.email


async def test_attributes(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            "media": {"camera_entity_id": "camera.doorbell"},
            "delivery": {"doorbell_chime_alexa": {"data": {"amazon_magic_id": "a77464"}}, "email": {}},
            "conditions": {
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

    assert attrs["delivery"]["doorbell_chime_alexa"]["data"]["amazon_magic_id"] == "a77464"


async def test_secondary_scenario(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITIONS: {"condition": "template", "value_template": '{{"scenario-possible-danger" in applied_scenarios}}'}
        }),
        hass_api,
    )
    assert await uut.validate()
    cvars = ConditionVariables(["scenario-no-danger", "sunny"], [], [], PRIORITY_MEDIUM, {})
    assert await uut.validate()
    assert not uut.evaluate(cvars)
    cvars.applied_scenarios.append("scenario-possible-danger")
    assert uut.evaluate(cvars)


async def test_scenario_unknown_var(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITIONS: {
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
            CONF_CONDITIONS: {
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
    assert uut.evaluate(ConditionVariables())
    hass.states.async_set("sensor.issues", "24")
    assert not uut.evaluate(ConditionVariables())


async def test_scenario_shortcut_style(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({CONF_CONDITIONS: "{{ (state_attr('device_tracker.iphone', 'battery_level')|int) > 50 }}"}),
        hass_api,
    )
    hass.states.async_set("device_tracker.iphone", "on", attributes={"battery_level": 12})
    assert await uut.validate()
    assert not uut.evaluate(ConditionVariables())
    hass.states.async_set("device_tracker.iphone", "on", attributes={"battery_level": 60})
    assert uut.evaluate(ConditionVariables())


async def test_trace(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    uut = Scenario(
        "testing",
        SCENARIO_SCHEMA({
            CONF_CONDITIONS: {"condition": "template", "value_template": "{{'scenario-alert' in applied_scenarios}}"}
        }),
        hass_api,
    )
    assert await uut.validate()
    assert await uut.trace(ConditionVariables(["scenario-alert"], [], [], PRIORITY_MEDIUM, {"AT_HOME": [{"name": "bob"}]}))
    assert uut.last_trace is not None
    _LOGGER.info("trace: %s", uut.last_trace.as_dict())
