from unittest.mock import AsyncMock, Mock

from homeassistant.const import CONF_CONDITION, CONF_CONDITIONS, CONF_ENTITY_ID, CONF_STATE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.util import dt as dt_util

from custom_components.supernotify import (
    ATTR_DUPE_POLICY_NONE,
    CONF_ACTION,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_DUPE_POLICY,
    CONF_OPTIONS,
    CONF_PHONE_NUMBER,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_TARGET,
    CONF_TARGET_REQUIRED,
    CONF_TRANSPORT,
    DELIVERY_SCHEMA,
    DELIVERY_SELECTION_EXPLICIT,
    PRIORITY_CRITICAL,
    SELECTION_BY_SCENARIO,
    SELECTION_FALLBACK,
    SELECTION_FALLBACK_ON_ERROR,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_EMAIL,
    TRANSPORT_GENERIC,
    TRANSPORT_PERSISTENT,
    TRANSPORT_SMS,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import TargetRequired
from custom_components.supernotify.notify import SupernotifyAction
from tests.supernotify.doubles_lib import DummyTransport

DELIVERY: dict[str, dict] = {
    "email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_TRANSPORT: TRANSPORT_CHIME, "target": ["switch.bell_1", "script.siren_2"]},
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_SELECTION: [SELECTION_BY_SCENARIO]},
    "dummy": {CONF_TRANSPORT: "dummy"},
}
SCENARIOS: dict[str, dict] = {
    "scenario1": {CONF_DELIVERY: {"persistent": {}}},
    "scenario2": {CONF_DELIVERY: {"persistent": {}}},
}

RECIPIENTS: list[dict] = [
    {
        "person": "person.new_home_owner",
        "email": "me@tester.net",
        CONF_PHONE_NUMBER: "+2301015050503",
        "mobile_devices": [{"mobile_app_id": "mobile_app_new_iphone"}],
        CONF_DELIVERY: {"dummy": {CONF_DATA: {"emoji_id": 912393}, CONF_TARGET: ["xyz123"]}},
    },
    {"person": "person.bidey_in", CONF_PHONE_NUMBER: "+4489393013834", CONF_DELIVERY: {"dummy": {CONF_TARGET: ["abc789"]}}},
]

TRANSPORT_DEFAULTS: dict[str, dict] = {
    TRANSPORT_GENERIC: {"delivery_defaults": {CONF_ACTION: "notify.slackity", CONF_ENTITY_ID: ["entity.1", "entity.2"]}},
    TRANSPORT_EMAIL: {"delivery_defaults": {CONF_OPTIONS: {"jpeg_opts": {"progressive": True}}}},
    "dummy": {"delivery_defaults": {CONF_TARGET_REQUIRED: False}},
}


async def test_send_message_with_explicit_scenario_delivery(mock_hass: Mock) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries=DELIVERY,
        scenarios=SCENARIOS,
        recipients=RECIPIENTS,
        transport_configs=TRANSPORT_DEFAULTS,
        dupe_check={CONF_DUPE_POLICY: ATTR_DUPE_POLICY_NONE},
    )
    await uut.initialize()
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT},
    )
    uut.context.hass_api._hass.services.async_call.assert_not_called()  # type: ignore
    uut.context.hass_api._hass.services.async_call.reset_mock()  # type: ignore

    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        # explicit selection implied by delivery list
        data={"delivery": ["persistent"]},
    )
    # explicit delivery selection overrides everything else
    uut.context.hass_api._hass.services.async_call.assert_called_with(  # type: ignore
        "persistent_notification",
        "create",
        service_data={"title": "test_title", "message": "testing 123", "notification_id": None},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
    uut.context.hass_api._hass.services.async_call.reset_mock()  # type: ignore
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={
            "delivery_selection": DELIVERY_SELECTION_EXPLICIT,
            "apply_scenarios": ["scenario1"],
        },
    )
    # scenario switches one delivery on
    uut.context.hass_api._hass.services.async_call.assert_called_with(  # type: ignore
        "persistent_notification",
        "create",
        service_data={"title": "test_title", "message": "testing 123", "notification_id": None},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_explicit_delivery_on_action(mock_hass: Mock) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries=DELIVERY,
        scenarios=SCENARIOS,
        recipients=RECIPIENTS,
        transport_configs=TRANSPORT_DEFAULTS,
        dupe_check={CONF_DUPE_POLICY: ATTR_DUPE_POLICY_NONE},
    )
    await uut.initialize()
    await uut.async_send_message(message="testing 123", data={"delivery": "text"})
    assert mock_hass.services.async_call.call_count == 1
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "sms",
        service_data={"message": "testing 123", "target": ["+2301015050503", "+4489393013834"]},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
    # contra-test
    mock_hass.services.async_call.reset_mock()
    await uut.async_send_message(message="testing 123")
    assert mock_hass.services.async_call.call_count == 6  # SMS + 2 notify + 2 chime + 1 mobile_push


async def test_recipient_delivery_data_override(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass, deliveries=DELIVERY, transport_configs=TRANSPORT_DEFAULTS, recipients=RECIPIENTS)
    dummy = DummyTransport(uut.context)
    uut.context.configure_for_tests(transport_instances=[dummy])
    await uut.initialize()

    # implicit person selection
    assert dummy is not None
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": {"pigeon": {}, "dummy": {}}},
    )

    assert len(dummy.service.calls) == 2
    assert dummy.service.calls[0].data["emoji_id"] == 912393
    assert "emoji_id" not in dummy.service.calls[1].data

    # explicit person selection
    assert dummy is not None
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={
            "target": "person.new_home_owner",
            "delivery_selection": DELIVERY_SELECTION_EXPLICIT,
            "delivery": {"pigeon": {}, "dummy": {}},
        },
    )

    assert len(dummy.service.calls) == 2
    assert dummy.service.calls[0].data["emoji_id"] == 912393
    assert "emoji_id" not in dummy.service.calls[1].data


async def test_recipient_delivery_target_override(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass, deliveries=DELIVERY, transport_configs=TRANSPORT_DEFAULTS, recipients=RECIPIENTS)
    dummy = DummyTransport(uut.context)
    uut.context.configure_for_tests(transport_instances=[dummy])
    await uut.initialize()

    assert dummy is not None
    await uut.async_send_message(
        message="testing 123",
        data={"delivery": "dummy"},
    )

    assert len(dummy.service.calls) == 2
    assert dummy.service.calls[0].data["_UNKNOWN_"] == ["xyz123"]
    assert dummy.service.calls[1].data["_UNKNOWN_"] == ["abc789"]
    assert dummy.service.calls[1].data["email"] == ["me@tester.net"]
    assert dummy.service.calls[1].data["mobile_app_id"] == ["mobile_app_new_iphone"]


async def test_delivery_to_broken_service(mock_hass: HomeAssistant) -> None:
    delivery_config = {"broken": {CONF_TRANSPORT: "dummy"}}
    uut = SupernotifyAction(mock_hass, deliveries=delivery_config, transport_configs=TRANSPORT_DEFAULTS, recipients=RECIPIENTS)
    broken = DummyTransport(
        uut.context, target_required=TargetRequired.OPTIONAL, service_exception=OSError("a self-inflicted error has occurred")
    )
    uut.context.configure_for_tests(transport_instances=[broken])
    await uut.initialize()

    before = dt_util.utcnow()
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": "broken"},
    )
    notification = uut.last_notification
    assert notification is not None
    assert len(notification.undelivered_envelopes) == 1
    assert isinstance(notification.undelivered_envelopes[0], Envelope)
    assert isinstance(notification.undelivered_envelopes[0].delivery_error, list)
    assert any("OSError" in stack for stack in notification.undelivered_envelopes[0].delivery_error)
    assert broken.error_count == 1
    assert broken.last_error_message == "a self-inflicted error has occurred"
    assert broken.last_error_in == "call_action"
    assert broken.last_error_at is not None
    assert broken.last_error_at >= before
    assert broken.last_error_at <= dt_util.utcnow()


async def test_delivery_to_broken_transport(mock_hass: HomeAssistant) -> None:
    delivery_config = {"broken": {CONF_TRANSPORT: "dummy"}}
    uut = SupernotifyAction(mock_hass, deliveries=delivery_config, transport_configs=TRANSPORT_DEFAULTS, recipients=RECIPIENTS)
    broken = DummyTransport(
        uut.context,
        target_required=TargetRequired.OPTIONAL,
        transport_exception=ValueError("a self-inflicted error has occurred"),
    )
    uut.context.configure_for_tests(transport_instances=[broken])
    await uut.initialize()

    before = dt_util.utcnow()
    await uut.async_send_message(
        title="test_title",
        message="testing 123",
        data={"delivery_selection": DELIVERY_SELECTION_EXPLICIT, "delivery": "broken"},
    )
    notification = uut.last_notification
    assert notification is not None
    assert len(notification.undelivered_envelopes) == 1
    assert isinstance(notification.undelivered_envelopes[0], Envelope)
    assert isinstance(notification.undelivered_envelopes[0].delivery_error, list)
    assert any("ValueError" in stack for stack in notification.undelivered_envelopes[0].delivery_error)
    assert broken.error_count == 1
    assert broken.last_error_at is not None
    assert broken.last_error_message == "a self-inflicted error has occurred"
    assert broken.last_error_in == "deliver"
    assert broken.last_error_at >= before
    assert broken.last_error_at <= dt_util.utcnow()


async def test_null_delivery(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass)
    await uut.initialize()
    await uut.async_send_message("just a test")
    mock_hass.services.async_call.assert_not_called()  # type: ignore


async def test_fallback_delivery_on_error(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "generic": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_SELECTION: [SELECTION_FALLBACK_ON_ERROR],
                CONF_ACTION: "notify.dummy",
            },
            "failing": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.make_fail"},
        },
        transport_configs=TRANSPORT_DEFAULTS,
    )

    def call_service(domain, service, service_data=None, **kwargs):
        if service == "make_fail":
            raise ValueError("just because")

    mock_hass.services.async_call = AsyncMock(side_effect=call_service)
    await uut.initialize()
    await uut.async_send_message("just a test", data={"priority": "low", "delivery": "failing"})
    mock_hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "dummy",
        service_data={"message": "just a test"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_fallback_delivery_by_default(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "generic": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_SELECTION: [SELECTION_FALLBACK], CONF_ACTION: "notify.dummy"},
            "failing": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.make_fail", CONF_PRIORITY: PRIORITY_CRITICAL},
        },
        transport_configs=TRANSPORT_DEFAULTS,
    )

    await uut.initialize()
    await uut.async_send_message("just a test", data={"priority": "low", "delivery": "failing"})
    mock_hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "dummy",
        service_data={"message": "just a test"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_send_message_with_conditions(hass: HomeAssistant) -> None:
    delivery = {
        CONF_TRANSPORT: TRANSPORT_GENERIC,
        CONF_ACTION: "testing.mock_notification",
        CONF_TARGET_REQUIRED: "never",
        CONF_CONDITIONS: {
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
    hass.states.async_set("alarm_control_panel.home_alarm_control", "disarmed")
    await hass.async_block_till_done()

    delivery_config = {"testablity": DELIVERY_SCHEMA(delivery)}
    uut = SupernotifyAction(hass, deliveries=delivery_config, recipients=RECIPIENTS)
    await uut.initialize()

    await uut.async_send_message(title="test_title", message="testing 123")
    await hass.async_block_till_done()
    assert calls_service_data == []
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_away")
    await hass.async_block_till_done()

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
