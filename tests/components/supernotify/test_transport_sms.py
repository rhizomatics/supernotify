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

    assert await uut.deliver(
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


async def test_empty_deliver() -> None:
    ctx = TestingContext(deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    assert not await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message=None),
            target=Target(["+447979123456"]),
        )
    )


async def test_deliver_with_data() -> None:
    ctx = TestingContext(deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    assert await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message="hello there"),
            target=Target(["+447979123456"]),
            data={"data": {"custom_field": "custom_value"}},
        )
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smsify",
        service_data={"message": "hello there", "target": ["+447979123456"], "data": {"custom_field": "custom_value"}},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_jumbo() -> None:
    ctx = TestingContext(deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    assert await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message="0123456789" * 20),
            target=Target(["+447979123456"]),
        )
    )
    truncated = "0123456789" * 15 + "01234567"
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smsify",
        service_data={"message": truncated, "target": ["+447979123456"]},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
