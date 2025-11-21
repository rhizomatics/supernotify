import time

from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext


async def test_simple_core_action_data() -> None:
    context = TestingContext()
    await context.test_initialize()

    envelope = Envelope(context.delivery("DEFAULT_notify_entity"),
                        notification=Notification(
        context,
        message="Hello Test",
        action_data={"key1": "value1"},
    ))
    assert envelope.core_action_data() == {"message": "Hello Test"}


async def test_timestamp_core_action_data() -> None:
    context = TestingContext()
    await context.test_initialize()

    envelope = Envelope(context.delivery("DEFAULT_notify_entity"),
                        notification=Notification(
        context,
        message="Hello Test"),
        data={"timestamp": "%Y"}
    )
    assert envelope.core_action_data(
    ) == {"message": f"Hello Test [{time.strftime('%Y', time.localtime())}]"}


async def test_equality() -> None:
    context = TestingContext()
    await context.test_initialize()
    notification = Notification(
        context,
        message="Hello Test")
    assert Envelope(context.delivery("DEFAULT_notify_entity"),
                    notification=notification) == Envelope(context.delivery("DEFAULT_notify_entity"),
                                                           notification=notification)
    assert Envelope(context.delivery("DEFAULT_notify_entity"),
                    notification=notification) != Envelope(context.delivery("DEFAULT_notify_entity"),
                                                           notification=notification, data={"extra": "data"})
    assert Envelope(context.delivery("DEFAULT_notify_entity"),
                    notification=notification) != Envelope(context.delivery("DEFAULT_notify_entity"),
                                                           notification=Notification(
                        context,
                        message="Hello Test"))


async def test_repr() -> None:
    context = TestingContext()
    await context.test_initialize()
    notification = Notification(
        context,
        message="Hello Test")
    envelope = Envelope(context.delivery("DEFAULT_notify_entity"),
                        notification=notification)
    assert repr(
        envelope) == "Envelope(message=Hello Test,title=None,delivery=DEFAULT_notify_entity)"
