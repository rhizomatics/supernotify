from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import CONF_DEFAULT

from custom_components.supernotify import ATTR_NOTIFICATION_ID, CONF_TRANSPORT, TRANSPORT_PERSISTENT
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.persistent import PersistentTransport


async def test_deliver(mock_hass, mock_people_registry, superconfig) -> None:  # type: ignore
    """Test on_notify_persistent"""
    context = superconfig
    await context.initialize()
    uut = PersistentTransport(mock_hass, context, {"pn": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_DEFAULT: True}})
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()
    await uut.deliver(Envelope("pn", Notification(context, mock_people_registry, "hello there", title="testing")))
    mock_hass.services.async_call.assert_called_with(
        "persistent_notification",
        "create",
        service_data={ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_NOTIFICATION_ID: None},
    )
