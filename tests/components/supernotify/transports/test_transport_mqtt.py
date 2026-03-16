from homeassistant.const import (
    CONF_NAME,
)

from custom_components.supernotify.const import CONF_DATA, CONF_TRANSPORT, TRANSPORT_MQTT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.mqtt import MQTTTransport
from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_deliver(mock_hass, mock_scenario_registry, uninitialized_unmocked_config) -> None:  # type: ignore
    deliveries = {
        "dive_dive_dive": {
            CONF_TRANSPORT: TRANSPORT_MQTT,
            CONF_NAME: "dive_dive_dive",
            CONF_DATA: {
                "topic": "zigbee2mqtt/Downstairs Siren/set",
                "payload": {
                    "warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}
                },
            },
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._config_deliveries = deliveries
    context.scenario_registry = mock_scenario_registry

    uut = MQTTTransport(context)

    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await context.delivery_registry.initialize(context)

    notification = Notification(context, message="Will be ignored", title="Also Ignored")
    await notification.initialize()
    await notification.deliver()

    context.hass_api.call_service.assert_called_with(
        "mqtt",
        "publish",
        service_data={
            "topic": "zigbee2mqtt/Downstairs Siren/set",
            "payload": '{"warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}}',  # noqa: E501
        },
        debug=False,
    )


def test_recipient_target_returns_none(mock_hass, uninitialized_unmocked_config) -> None:  # type: ignore
    uut = MQTTTransport(uninitialized_unmocked_config)
    result = uut.recipient_target({"person": "person.test"})
    assert result is None


async def test_deliver_warns_on_missing_topic() -> None:
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_DATA: {"payload": "hello"},
            }
        }
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MQTT)
    n = Notification(ctx, message="ignored")
    await n.initialize()
    envelope = Envelope(
        Delivery("broker", ctx.delivery_config("broker"), uut),
        n,
        data={"payload": "hello"},
    )
    await uut.deliver(envelope)
