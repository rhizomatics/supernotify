from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.core import HomeAssistant

from custom_components.supernotify.const import CONF_TRANSPORT, TRANSPORT_PERSISTENT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.persistent import PersistentTransport
from tests.components.supernotify.hass_setup_lib import TestingContext
from tests.components.supernotify.transports.schema_usage import SchemaCase, assert_schema_usage, sizes


async def test_deliver() -> None:  # type: ignore
    """Test on_notify_persistent"""
    ctx = TestingContext(deliveries={"pn": {CONF_TRANSPORT: TRANSPORT_PERSISTENT}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PERSISTENT)

    await uut.deliver(
        Envelope(Delivery("pn", ctx.delivery_config("pn"), uut), Notification(ctx, "hello there", title="testing"))
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "persistent_notification",
        "create",
        service_data={ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


@sizes
async def test_schema_usage(hass: HomeAssistant, maximal: bool) -> None:
    case = SchemaCase(
        PersistentTransport,
        expected={"persistent_notification.create"},
        maximal_data={"notification_id": "porch_alert"},
    )
    await assert_schema_usage(hass, case, maximal)
