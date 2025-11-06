from homeassistant.const import CONF_DEFAULT, CONF_METHOD, CONF_NAME

from custom_components.supernotify import CONF_DATA, METHOD_MQTT
from custom_components.supernotify.context import Context
from custom_components.supernotify.methods.mqtt import MQTTDeliveryMethod
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass, mock_people_registry) -> None:  # type: ignore
    deliveries = {
        "dive_dive_dive": {
            CONF_METHOD: METHOD_MQTT,
            CONF_NAME: "teleport",
            CONF_DEFAULT: True,
            CONF_DATA: {
                "topic": "zigbee2mqtt/Downstairs Siren/set",
                "payload": {
                    "warning": {
                        "duration": 30,
                        "mode": "emergency",
                        "level": "low",
                        "strobe": "true",
                        "strobe_duty_cycle": 10
                    }
                }
            }
        }
    }
    context = Context(deliveries=deliveries)
    uut = MQTTDeliveryMethod(
        mock_hass,
        context,
        mock_people_registry,
        deliveries=deliveries
    )

    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    notification = Notification(
        context,
        mock_people_registry,
        message="Will be ignored",
        title="Also Ignored"
    )
    await notification.initialize()
    await notification.deliver()

    mock_hass.services.async_call.assert_called_with(
        "mqtt",
        "publish",
        service_data={
            "topic": "zigbee2mqtt/Downstairs Siren/set",
            "payload": '{"warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}}'},
    )
