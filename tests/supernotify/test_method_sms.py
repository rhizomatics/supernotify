from homeassistant.const import CONF_ACTION, CONF_DEFAULT

from custom_components.supernotify import CONF_PERSON, CONF_PHONE_NUMBER, CONF_TRANSPORT, TRANSPORT_SMS
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.sms import SMSTransport


async def test_deliver(mock_hass, mock_people_registry, uninitialized_superconfig) -> None:  # type: ignore
    """Test on_notify_email."""
    delivery_config = {"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_DEFAULT: True, CONF_ACTION: "notify.smsify"}}
    context = uninitialized_superconfig
    context._recipients = [{CONF_PERSON: "person.tester1", CONF_PHONE_NUMBER: "+447979123456"}]
    context._deliveries = delivery_config

    uut = SMSTransport(mock_hass, context, mock_people_registry, delivery_config)
    context.configure_for_tests([uut])
    await context.initialize()

    await uut.initialize()
    await uut.deliver(
        Envelope(
            "smsify",
            Notification(context, mock_people_registry, message="hello there", title="testing"),
            target=Target(["+447979123456"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify", "smsify", service_data={"message": "testing hello there", "target": ["+447979123456"]}
    )
    mock_hass.reset_mock()
    await uut.deliver(
        Envelope(
            "smsify",
            Notification(context, mock_people_registry, message="explicit target", title="testing"),
            target=Target(["+19876123456"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smsify",
        service_data={
            "message": "testing explicit target",
            "target": ["+19876123456"],
        },
    )
