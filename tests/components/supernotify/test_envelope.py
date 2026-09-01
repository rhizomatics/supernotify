import time
import types
from unittest.mock import MagicMock, patch

from jinja2 import TemplateError

from custom_components.supernotify.const import CONF_TRANSPORT
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import DeliveryCustomization, MessageOnlyPolicy, TargetRequired
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


async def test_customize_data_empty_input_short_circuits() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(context.delivery("DEFAULT_notify_entity"))
    assert uut.customize_data({}) == {}


async def test_core_action_data_no_message_with_force() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(context.delivery("DEFAULT_notify_entity"))
    data = uut.core_action_data(force_message=True)
    assert data["message"] == ""


async def test_contents_excludes_target_when_never_required() -> None:
    context = TestingContext()
    await context.test_initialize()
    delivery = context.delivery("DEFAULT_notify_entity")
    delivery.target_required = TargetRequired.NEVER
    uut = Envelope(delivery, Notification(context, message="hello there"))
    assert "target" not in uut.contents(minimal=True)


async def test_eq_against_non_envelope_and_none() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(context.delivery("DEFAULT_notify_entity"), Notification(context, message="hello there"))
    none_value = None
    assert uut != none_value
    assert uut != "not an envelope"


async def test_compute_message_renders_template_string() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        Notification(context, message="{{ 1 + 1 }}"),
        context=context,
    )
    assert uut.message == "2"


async def test_compute_message_template_render_exception_keeps_raw_message() -> None:
    context = TestingContext()
    await context.test_initialize()
    with patch.object(context.hass_api, "template", side_effect=Exception("boom")):
        uut = Envelope(
            context.delivery("DEFAULT_notify_entity"),
            Notification(context, message="{{ 1 + 1 }}"),
            context=context,
        )
    assert uut.message == "{{ 1 + 1 }}"


async def test_render_scenario_templates_missing_condition_variables_defaults_to_empty() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        Notification(context, message="hello there"),
        context=context,
    )
    uut.condition_variables = None  # type: ignore[assignment]
    fake_scenario = types.SimpleNamespace(
        delivery_config=lambda _name: DeliveryCustomization({"data": {"message_template": "{{ notification_message }} EXTRA"}})
    )
    uut._enabled_scenarios = {"fake": fake_scenario}  # type: ignore[dict-item]

    result = uut._render_scenario_templates("hello there", "message_template", "notification_message")
    assert result == "hello there EXTRA"


async def test_render_scenario_templates_template_error_is_caught() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        Notification(context, message="hello there"),
        context=context,
    )
    fake_scenario = types.SimpleNamespace(
        delivery_config=lambda _name: DeliveryCustomization({"data": {"message_template": "{{ broken"}})
    )
    uut._enabled_scenarios = {"fake": fake_scenario}  # type: ignore[dict-item]
    broken_template = MagicMock()
    broken_template.async_render.side_effect = TemplateError("bad template")

    with patch.object(context.hass_api, "template", return_value=broken_template):
        result = uut._render_scenario_templates("hello there", "message_template", "notification_message")

    assert result == "hello there"
    assert uut.error_count == 1


async def test_resolve_data_templates_renders_template_values() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        Notification(context, message="hello there"),
        context=context,
    )
    resolved = uut._resolve_data_templates({"greeting": "{{ 1 + 1 }}", "plain": "unchanged"})
    assert resolved["greeting"] == "2"
    assert resolved["greeting_template"] == "{{ 1 + 1 }}"
    assert resolved["plain"] == "unchanged"


async def test_resolve_data_templates_keeps_raw_value_on_render_exception() -> None:
    context = TestingContext()
    await context.test_initialize()
    uut = Envelope(
        context.delivery("DEFAULT_notify_entity"),
        Notification(context, message="hello there"),
        context=context,
    )
    with patch.object(context.hass_api, "template", side_effect=Exception("boom")):
        resolved = uut._resolve_data_templates({"greeting": "{{ 1 + 1 }}"})
    assert resolved["greeting"] == "{{ 1 + 1 }}"
    assert "greeting_template" not in resolved
