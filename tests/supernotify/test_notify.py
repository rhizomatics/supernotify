from unittest.mock import Mock

from homeassistant.const import CONF_CONDITION, CONF_CONDITIONS, CONF_ENTITY_ID, CONF_STATE
from homeassistant.core import HomeAssistant, ServiceCall, callback

from custom_components.supernotify import (
    ATTR_DUPE_POLICY_NONE,
    ATTR_PRIORITY,
    CONF_ACTION,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_DUPE_POLICY,
    CONF_METHOD,
    CONF_OPTIONS,
    CONF_PHONE_NUMBER,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_TARGET,
    CONF_TARGETS_REQUIRED,
    DELIVERY_SCHEMA,
    DELIVERY_SELECTION_EXPLICIT,
    METHOD_ALEXA_MEDIA_PLAYER,
    METHOD_CHIME,
    METHOD_EMAIL,
    METHOD_GENERIC,
    METHOD_MOBILE_PUSH,
    METHOD_PERSISTENT,
    METHOD_SMS,
    SCENARIO_DEFAULT,
    SELECTION_BY_SCENARIO,
    SELECTION_FALLBACK,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import SuperNotificationAction
from tests.supernotify.doubles_lib import BrokenDeliveryMethod, DummyDeliveryMethod

DELIVERY: dict[str, dict] = {
    "email": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_METHOD: METHOD_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_METHOD: METHOD_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_media_player": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_METHOD: METHOD_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_METHOD: METHOD_PERSISTENT, CONF_SELECTION: SELECTION_BY_SCENARIO},
    "dummy": {CONF_METHOD: "dummy"},
}
SCENARIOS: dict[str, dict] = {
    SCENARIO_DEFAULT: {CONF_DELIVERY: {"alexa_devices": {}, "chime": {}, "text": {}, "email": {}, "chat": {}}},
    "scenario1": {CONF_DELIVERY: {"persistent": {}}},
    "scenario2": {CONF_DELIVERY: {"persistent": {}}},
}

RECIPIENTS: list[dict] = [
    {
        "person": "person.new_home_owner",
        "email": "me@tester.net",
        CONF_PHONE_NUMBER: "+2301015050503",
        "mobile_devices": [{"notify_action": "mobile_app_new_iphone"}],
        CONF_DELIVERY: {"dummy": {CONF_DATA: {"emoji_id": 912393}, CONF_TARGET: ["xyz123"]}},
    },
    {"person": "person.bidey_in", CONF_PHONE_NUMBER: "+4489393013834", CONF_DELIVERY: {"dummy": {CONF_TARGET: ["abc789"]}}},
]

METHOD_DEFAULTS: dict[str, dict] = {
    METHOD_GENERIC: {"default": {CONF_ACTION: "notify.slackity", CONF_ENTITY_ID: ["entity.1", "entity.2"]}},
    METHOD_EMAIL: {"default": {CONF_OPTIONS: {"jpeg_opts": {"progressive": True}}}},
    "dummy": {CONF_TARGETS_REQUIRED: False},
}


async def test_send_message_with_scenario_mismatch(mock_hass: Mock) -> None:
    uut = SuperNotificationAction(
        mock_hass,
        deliveries=DELIVERY,
        scenarios=SCENARIOS,
        recipients=RECIPIENTS,
        method_configs=METHOD_DEFAULTS,
        dupe_check={CONF_DUPE_POLICY: ATTR_DUPE_POLICY_NONE},
    )
    await uut.initialize()
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": {"pigeon": {}, "persistent": {}}},
    )
    mock_hass.services.async_call.assert_not_called()
    mock_hass.reset_mock()
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={
            "delivery_selection": DELIVERY_SELECTION_EXPLICIT,
            "delivery": {"pigeon": {}, "persistent": {}},
            "apply_scenarios": ["scenario1"],
        },
    )
    mock_hass.services.async_call.assert_called_with(
        "persistent_notification",
        "create",
        service_data={"title": "test_title", "message": "testing 123", "notification_id": None},
    )


async def test_recipient_delivery_data_override(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(mock_hass, deliveries=DELIVERY, method_configs=METHOD_DEFAULTS, recipients=RECIPIENTS)
    dummy = DummyDeliveryMethod(mock_hass, uut.context, {})
    uut.context.configure_for_tests(method_instances=[dummy])
    await uut.initialize()

    assert dummy is not None
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": {"pigeon": {}, "dummy": {}}},
    )

    assert len(dummy.test_calls) == 2
    assert dummy.test_calls == [
        Envelope("dummy", uut.last_notification, targets=["dummy.new_home_owner", "xyz123"], data={"emoji_id": 912393}),
        Envelope("dummy", uut.last_notification, targets=["dummy.bidey_in", "abc789"]),
    ]


async def test_broken_delivery(mock_hass: HomeAssistant) -> None:
    delivery_config = {"broken": {CONF_METHOD: "broken"}}
    uut = SuperNotificationAction(mock_hass, deliveries=delivery_config, method_configs=METHOD_DEFAULTS, recipients=RECIPIENTS)
    broken = BrokenDeliveryMethod(mock_hass, uut.context, delivery_config)
    uut.context.configure_for_tests(method_instances=[broken])
    await uut.initialize()

    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": {"broken"}},
    )
    notification = uut.last_notification
    assert notification is not None
    assert len(notification.undelivered_envelopes) == 1
    assert isinstance(notification.undelivered_envelopes[0], Envelope)
    assert isinstance(notification.undelivered_envelopes[0].delivery_error, list)
    assert len(notification.undelivered_envelopes[0].delivery_error) == 4
    assert notification.undelivered_envelopes[0].delivery_error[3] == "OSError: a self-inflicted error has occurred\n"


async def test_null_delivery(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(mock_hass)
    await uut.initialize()
    await uut.async_send_message("just a test")
    mock_hass.services.async_call.assert_not_called()  # type: ignore


async def test_fallback_delivery(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(
        mock_hass,
        deliveries={
            "generic": {CONF_METHOD: METHOD_GENERIC, CONF_SELECTION: SELECTION_FALLBACK, CONF_ACTION: "notify.dummy"},
            "push": {CONF_METHOD: METHOD_MOBILE_PUSH, CONF_ACTION: "notify.push", CONF_PRIORITY: "critical"},
        },
        method_configs=METHOD_DEFAULTS,
    )
    await uut.initialize()
    await uut.async_send_message("just a test", data={"priority": "low"})
    mock_hass.services.async_call.assert_called_once_with(  # type: ignore
        "notify", "dummy", service_data={"message": "just a test", "data": {}}
    )


async def test_send_message_with_condition(hass: HomeAssistant) -> None:
    delivery = {
        CONF_METHOD: METHOD_GENERIC,
        CONF_ACTION: "testing.mock_notification",
        CONF_CONDITION: {
            CONF_CONDITION: "or",
            CONF_CONDITIONS: [
                {
                    CONF_CONDITION: "state",
                    CONF_ENTITY_ID: "alarm_control_panel.home_alarm_control",
                    CONF_STATE: ["armed_away", "armed_night"],
                },
                {
                    CONF_CONDITION: "template",
                    "value_template": "{{notification_priority in ['critical', 'high'] and notification_message != 'test'}}",
                },
            ],
        },
    }

    calls_service_data = []

    @callback
    def mock_service_log(call: ServiceCall):
        calls_service_data.append(call.data)

    hass.services.async_register(
        "testing",
        "mock_notification",
        mock_service_log,
    )
    delivery_config = {"testablity": DELIVERY_SCHEMA(delivery)}
    uut = SuperNotificationAction(hass, deliveries=delivery_config, recipients=RECIPIENTS)
    await uut.initialize()
    hass.states.async_set("alarm_control_panel.home_alarm_control", "disarmed")

    await uut.async_send_message(title="test_title", message="testing 123")
    await hass.async_block_till_done()
    assert calls_service_data == []
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_away")

    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"priority": "high", "delivery": {"testablity": {CONF_DATA: {"test": "unit"}}}},
    )
    await hass.async_block_till_done()
    assert calls_service_data == [{"test": "unit"}]

    calls_service_data.clear()
    hass.states.async_set("alarm_control_panel.home_alarm_control", "disarmed")
    await uut.async_send_message(
        title="test_title",
        message="test",
        data={"priority": "high", "delivery": {"testablity": {CONF_DATA: {"test": "unit"}}}},
    )
    await hass.async_block_till_done()
    assert calls_service_data == []

    calls_service_data.clear()
    await uut.async_send_message(
        title="test_title",
        message="for real",
        data={"priority": "high", "delivery": {"testablity": {CONF_DATA: {"test": "unit"}}}},
    )
    await hass.async_block_till_done()
    assert calls_service_data == [{"test": "unit"}]


async def test_dupe_check_suppresses_same_priority_and_message(mock_hass: HomeAssistant) -> None:
    context = Mock(spec=Context)
    uut = SuperNotificationAction(mock_hass)
    await uut.initialize()
    n1 = Notification(context, "message here", "title here")
    assert uut.dupe_check(n1) is False
    n2 = Notification(context, "message here", "title here")
    assert uut.dupe_check(n2) is True


async def test_dupe_check_allows_higher_priority_and_same_message(mock_hass: HomeAssistant) -> None:
    context = Mock(Context)
    uut = SuperNotificationAction(mock_hass)
    await uut.initialize()
    n1 = Notification(context, "message here", "title here")
    assert uut.dupe_check(n1) is False
    n2 = Notification(context, "message here", "title here", action_data={ATTR_PRIORITY: "high"})
    assert uut.dupe_check(n2) is False
