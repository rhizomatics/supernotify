from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import CONF_DEFAULT

from custom_components.supernotify import ATTR_NOTIFICATION_ID, CONF_METHOD, METHOD_PERSISTENT
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.persistent import PersistentDeliveryMethod
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass) -> None:  # type: ignore
    """Test on_notify_persistent"""
    context = Context()
    await context.initialize()
    uut = PersistentDeliveryMethod(mock_hass, context, {"pn": {CONF_METHOD: METHOD_PERSISTENT, CONF_DEFAULT: True}})
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()
    await uut.deliver(Envelope("pn", Notification(context, "hello there", title="testing")))
    mock_hass.services.async_call.assert_called_with(
        "persistent_notification",
        "create",
        service_data={ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_NOTIFICATION_ID: None},
    )
