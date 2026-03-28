import time

from custom_components.supernotify.const import CONF_TRANSPORT
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext


async def test_simple_core_action_data() -> None:
    context = TestingContext()
    await context.test_initialize()

    envelope = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        notification=Notification(
            context,
            message="Hello Test",
            action_data={"key1": "value1"},
        ),
    )
    assert envelope.core_action_data() == {"message": "Hello Test"}


async def test_timestamp_core_action_data() -> None:
    context = TestingContext()
    await context.test_initialize()

    envelope = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        notification=Notification(context, message="Hello Test"),
        data={"timestamp": "%Y"},
    )
    assert envelope.core_action_data() == {"message": f"Hello Test [{time.strftime('%Y', time.localtime())}]"}


async def test_equality() -> None:
    context = TestingContext()
    await context.test_initialize()
    notification = Notification(context, message="Hello Test")
    assert Envelope(context.delivery("DEFAULT_notify_entity"), notification=notification) == Envelope(
        context.delivery("DEFAULT_notify_entity"), notification=notification
    )
    assert Envelope(context.delivery("DEFAULT_notify_entity"), notification=notification) != Envelope(
        context.delivery("DEFAULT_notify_entity"), notification=notification, data={"extra": "data"}
    )
    assert Envelope(context.delivery("DEFAULT_notify_entity"), notification=notification) != Envelope(
        context.delivery("DEFAULT_notify_entity"), notification=Notification(context, message="Hello Test")
    )


async def test_repr() -> None:
    context = TestingContext()
    await context.test_initialize()
    notification = Notification(context, message="Hello Test")
    envelope = Envelope(context.delivery("DEFAULT_notify_entity"), notification=notification)
    assert repr(envelope) == "Envelope(message=Hello Test,title=None,delivery=DEFAULT_notify_entity)"


async def test_message_usage() -> None:
    ctx = TestingContext(deliveries={"push": {CONF_TRANSPORT: "notify_entity"}})
    await ctx.test_initialize()
    delivery = ctx.delivery("push")

    uut = Envelope(delivery, Notification(ctx, "testing 123", title="the big title"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() == "the big title"

    delivery.options["message_usage"] = MessageOnlyPolicy.USE_TITLE
    uut = Envelope(delivery, Notification(ctx, "testing 123", title="the big title"))
    assert uut._compute_message() == "the big title"
    assert uut._compute_title() is None

    delivery.options["message_usage"] = MessageOnlyPolicy.USE_TITLE
    uut = Envelope(delivery, Notification(ctx, "testing 123"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() is None

    delivery.options["message_usage"] = MessageOnlyPolicy.COMBINE_TITLE
    uut = Envelope(delivery, Notification(ctx, "testing 123", title="the big title"))
    assert uut._compute_message() == "the big title testing 123"
    assert uut._compute_title() is None

    delivery.options["message_usage"] = MessageOnlyPolicy.COMBINE_TITLE
    uut = Envelope(delivery, Notification(ctx, "testing 123"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() is None


async def test_envelope_without_notification() -> None:
    context = TestingContext()
    await context.test_initialize()
    delivery = context.delivery("DEFAULT_notify_entity")
    # Lines 82-84: no notification branch sets empty _enabled_scenarios and uuid id
    uut = Envelope(delivery)
    assert uut._enabled_scenarios == {}
    assert uut.message is None
    assert uut.notification_id is None


async def test_core_action_data_no_message_no_force() -> None:
    context = TestingContext()
    await context.test_initialize()
    # Lines 129-130: message is None and force_message=False => no message key
    uut = Envelope(context.delivery("DEFAULT_notify_entity"))
    data = uut.core_action_data(force_message=False)
    assert "message" not in data


async def test_grab_image_without_notification() -> None:
    context = TestingContext()
    await context.test_initialize()
    # Line 165: grab_image returns None when no notification
    uut = Envelope(context.delivery("DEFAULT_notify_entity"))
    result = await uut.grab_image()
    assert result is None
