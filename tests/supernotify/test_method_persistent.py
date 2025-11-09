from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import CONF_DEFAULT

from conftest import TestingContext
from custom_components.supernotify import ATTR_NOTIFICATION_ID, CONF_TRANSPORT, TRANSPORT_PERSISTENT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification


async def test_deliver() -> None:  # type: ignore
    """Test on_notify_persistent"""
    ctx = TestingContext(deliveries={"pn": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_DEFAULT: True}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PERSISTENT)

    await uut.deliver(Envelope(Delivery("pn", ctx.deliveries["pn"], uut), Notification(ctx, "hello there", title="testing")))
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "persistent_notification",
        "create",
        service_data={ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_NOTIFICATION_ID: None},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
