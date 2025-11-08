from homeassistant.const import (
    CONF_DEFAULT,
    CONF_NAME,
)

from custom_components.supernotify import CONF_DATA, CONF_TRANSPORT, TRANSPORT_MQTT
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.mqtt import MQTTTransport


async def test_deliver(mock_hass, mock_people_registry, mock_scenario_registry, uninitialized_superconfig) -> None:  # type: ignore
    deliveries = {
        "dive_dive_dive": {
            CONF_TRANSPORT: TRANSPORT_MQTT,
            CONF_NAME: "dive_dive_dive",
            CONF_DEFAULT: True,
            CONF_DATA: {
                "topic": "zigbee2mqtt/Downstairs Siren/set",
                "payload": {
                    "warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}
                },
            },
        }
    }
    context = uninitialized_superconfig
    context._deliveries = deliveries
    mock_scenario_registry.delivery_by_scenario = {"DEFAULT": ["dive_dive_dive"]}
    context.scenario_registry = mock_scenario_registry

    uut = MQTTTransport(mock_hass, context, mock_people_registry, deliveries=deliveries)

    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()

    notification = Notification(context, mock_people_registry, message="Will be ignored", title="Also Ignored")
    await notification.initialize()
    await notification.deliver()

    mock_hass.services.async_call.assert_called_with(
        "mqtt",
        "publish",
        service_data={
            "topic": "zigbee2mqtt/Downstairs Siren/set",
            "payload": '{"warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}}',  # noqa: E501
        },
    )
