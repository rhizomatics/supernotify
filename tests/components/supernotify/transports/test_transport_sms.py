import string

from homeassistant.const import CONF_ACTION
from homeassistant.core import HomeAssistant

from custom_components.supernotify.const import CONF_TRANSPORT, TRANSPORT_SMS
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import SuppressionReason, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.sms import SMSTransport
from tests.components.supernotify.hass_setup_lib import TestingContext
from tests.components.supernotify.transports.schema_usage import SchemaCase, assert_schema_usage, sizes


async def test_deliver() -> None:
    """Test on_notify_email."""
    ctx = TestingContext(
        deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        viable_transport_types=[SMSTransport],
    )
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
    ctx = TestingContext(
        deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    envelope = Envelope(
        Delivery("smsify", ctx.delivery_config("smsify"), uut),
        Notification(ctx, message=None),
        target=Target(["+447979123456"]),
    )
    assert not await uut.deliver(envelope)
    assert envelope.skip_reason == SuppressionReason.INVALID_ACTION_DATA


async def test_simplify_keeps_currency_and_brackets() -> None:
    ctx = TestingContext(
        deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message="\U0001f6a8 Bill £20 + $5 (call 0141 555 1234) <now> https://x.org/a", title=None),
            target=Target(["+447979123456"]),
        )
    )
    assert ctx.hass.services.async_call.call_args.kwargs["service_data"]["message"] == (  # type:ignore
        " Bill £20 + $5 (call 0141 555 1234) <now> https://x.org/a"
    )


async def test_deliver_with_data() -> None:
    ctx = TestingContext(
        deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        viable_transport_types=[SMSTransport],
    )
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
    ctx = TestingContext(
        deliveries={"smsify": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    assert await uut.deliver(
        Envelope(
            Delivery("smsify", ctx.delivery_config("smsify"), uut),
            Notification(ctx, message=string.digits * 20),
            target=Target(["+447979123456"]),
        )
    )
    truncated = string.digits * 15 + string.octdigits
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smsify",
        service_data={"message": truncated, "target": ["+447979123456"]},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


@sizes
async def test_schema_usage(hass: HomeAssistant, maximal: bool) -> None:
    case = SchemaCase(
        SMSTransport,
        ["+447979123456"],
        {"notify.smsify"},
        delivery={"action": "notify.smsify"},
        maximal_data={"data": {"sender": "Home"}},
    )
    await assert_schema_usage(hass, case, maximal)
