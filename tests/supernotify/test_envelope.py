import time
from unittest.mock import Mock

from custom_components.supernotify import (
    DELIVERY_SELECTION_IMPLICIT,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
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


def test_message_usage(mock_context: Context) -> None:
    delivery = Mock(spec=Delivery, title=None, message=None, selection=DELIVERY_SELECTION_IMPLICIT)
    delivery.name="push"
    mock_context.delivery_registry.deliveries = {"push": delivery}
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["push"]}

    uut = Envelope(delivery,Notification(mock_context, "testing 123", title="the big title"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() == "the big title"

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Envelope(delivery,Notification(mock_context, "testing 123", title="the big title"))
    assert uut._compute_message() == "the big title"
    assert uut._compute_title() is None

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Envelope(delivery,Notification(mock_context, "testing 123"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Envelope(delivery,Notification(mock_context, "testing 123", title="the big title"))
    assert uut._compute_message() == "the big title testing 123"
    assert uut._compute_title() is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Envelope(delivery,Notification(mock_context, "testing 123"))
    assert uut._compute_message() == "testing 123"
    assert uut._compute_title() is None
