from homeassistant.const import CONF_ACTION

from custom_components.supernotify.const import CONF_TRANSPORT, TRANSPORT_SMS
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext


async def test_deliver() -> None:
    """Test on_notify_email."""
    ctx = TestingContext(deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message="hello there", title="testing"),
            target=Target(["+447979123456"]),
        )
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smsify",
        service_data={"message": "testing hello there", "target": ["+447979123456"]},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
    ctx.hass.services.async_call.reset_mock()  # type: ignore
    await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message="explicit target", title="testing"),
            target=Target(["+19876123456"]),
        )
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smsify",
        service_data={
            "message": "testing explicit target",
            "target": ["+19876123456"],
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
