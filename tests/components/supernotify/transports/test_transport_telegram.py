"""Tests for Telegram transport in SuperNotify."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_TARGET

from custom_components.supernotify.const import (
    ATTR_ACTIONS,
    ATTR_PHONE,
    ATTR_PRIORITY,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
    TRANSPORT_TELEGRAM,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import TransportFeature
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.telegram import (
    TelegramTransport,
    _build_inline_keyboard,
    _normalise_inline_keyboard,
)
from tests.components.supernotify.hass_setup_lib import TestingContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx() -> TestingContext:
    return TestingContext(
        deliveries={"telegram_test": {CONF_TRANSPORT: TRANSPORT_TELEGRAM}},
        transport_types=[TelegramTransport],
    )


def _mock_hass_api() -> MagicMock:
    mock = MagicMock()
    mock.call_service = AsyncMock(return_value={})
    mock.media_web_path = None
    return mock


def _envelope(
    ctx: TestingContext,
    message: str = "Test telegram",
    title: str | None = None,
    data: dict | None = None,
    media: dict | None = None,
    priority: str | None = None,
    chat_id: str | None = "123456789",
) -> Envelope:
    """Build a real Envelope for deliver(). chat_id delivered via telegram_chat_id data key."""
    action_data: dict = {}
    if priority:
        action_data[ATTR_PRIORITY] = priority
    if media:
        action_data["media"] = media

    merged: dict = {}
    if chat_id is not None:
        merged["telegram_chat_id"] = chat_id
    if data:
        merged.update(data)  # caller data overrides the default chat_id

    uut = ctx.transport(TRANSPORT_TELEGRAM)
    return Envelope(
        Delivery("telegram_test", ctx.delivery_config("telegram_test"), uut),
        Notification(ctx, message=message, title=title, action_data=action_data or None),
        data=merged or None,
    )


# ---------------------------------------------------------------------------
# Supported features
# ---------------------------------------------------------------------------


def test_supported_features() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    features = uut.supported_features
    assert features & TransportFeature.MESSAGE
    assert features & TransportFeature.TITLE
    assert features & TransportFeature.IMAGES
    assert features & TransportFeature.ACTIONS
    assert features & TransportFeature.SNAPSHOT_IMAGE


def test_default_config() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    config = uut.default_config
    assert config.delivery_defaults.action == "telegram_bot.send_message"


# ---------------------------------------------------------------------------
# Happy path delivery
# ---------------------------------------------------------------------------


async def test_deliver_basic_message() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Hello from SuperNotify"))

    assert result is True
    mock_api.call_service.assert_called_once()


async def test_deliver_message_with_title() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="This is the body", title="Important Alert", priority="high")
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    # Title is prepended to message, not a separate key
    assert "Important Alert" in service_data["message"]
    assert "This is the body" in service_data["message"]


async def test_deliver_critical_priority() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="CRITICAL ALERT", priority=PRIORITY_CRITICAL))

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    # critical priority maps to disable_notification=False → key absent
    assert service_data.get("disable_notification") is not True


async def test_deliver_minimum_priority() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Low priority message", priority=PRIORITY_MINIMUM))

    assert result is True


# ---------------------------------------------------------------------------
# Telegram-specific data keys
# ---------------------------------------------------------------------------


async def test_deliver_with_parse_mode_html() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="<b>Bold text</b>", data={"telegram_parse_mode": "HTML"})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data.get("parse_mode") == "html"  # normalised to lowercase
    assert "telegram_parse_mode" not in service_data


async def test_deliver_with_parse_mode_markdown() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="**Bold text**", data={"telegram_parse_mode": "Markdown"})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data.get("parse_mode") == "markdown"


async def test_deliver_with_disable_notification() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Silent message", data={"telegram_disable_notification": True})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data.get("disable_notification") is True


async def test_deliver_with_protect_content() -> None:
    """protect_content is accepted but intentionally NOT forwarded to the HA service."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Protected content", data={"telegram_protect_content": True})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "protect_content" not in service_data
    assert "telegram_protect_content" not in service_data


async def test_deliver_with_chat_id_override() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    # telegram_chat_id in data overrides the default chat_id from _envelope
    e = _envelope(ctx, message="Override test", data={"telegram_chat_id": "987654321"})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [987654321]


async def test_deliver_with_reply_to_message_id() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Reply to previous message", data={"telegram_reply_to_message_id": 42})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data.get("reply_to_message_id") == 42


# ---------------------------------------------------------------------------
# Image handling
# ---------------------------------------------------------------------------


async def test_deliver_with_attached_image() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    image_path = "/tmp/snapshot.jpg"
    e = _envelope(ctx, message="Here's the snapshot", title="Test Title", data={"telegram_attach_image": True})
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        e, "grab_image", new_callable=AsyncMock, return_value=Path(image_path)
    ):
        result = await uut.deliver(e)

    assert result is True
    call_args = mock_api.call_service.call_args
    assert call_args.args[1] == "send_photo"
    service_data = call_args.kwargs["service_data"]
    assert service_data["file"] == image_path
    assert "Test Title" in service_data["caption"]
    assert "Here's the snapshot" in service_data["caption"]
    assert service_data["parse_mode"] == "plain_text"


async def test_deliver_with_image_as_document() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    image_path = "/tmp/snapshot.jpg"
    e = _envelope(
        ctx,
        message="Document format image",
        title="Test Title",
        data={"telegram_attach_image": True, "telegram_image_as_document": True},
    )
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        e, "grab_image", new_callable=AsyncMock, return_value=Path(image_path)
    ):
        result = await uut.deliver(e)

    assert result is True
    call_args = mock_api.call_service.call_args
    assert call_args.args[1] == "send_document"
    service_data = call_args.kwargs["service_data"]
    assert service_data["file"] == image_path
    assert service_data["parse_mode"] == "plain_text"


async def test_deliver_image_not_found() -> None:
    """grab_image returning None falls back to text message delivery."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Image unavailable", data={"telegram_attach_image": True})
    with __import__("unittest.mock", fromlist=["patch"]).patch.object(
        e, "grab_image", new_callable=AsyncMock, return_value=None
    ):
        result = await uut.deliver(e)

    assert result is True
    call_args = mock_api.call_service.call_args
    assert call_args.args[1] == "send_message"
    service_data = call_args.kwargs["service_data"]
    assert "file" not in service_data


# ---------------------------------------------------------------------------
# Action buttons (inline keyboard)
# ---------------------------------------------------------------------------


async def test_deliver_with_action_buttons() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    actions = [{"title": "Accept", "action": "accept"}, {"title": "Decline", "action": "decline"}]
    e = Envelope(
        Delivery("telegram_test", ctx.delivery_config("telegram_test"), uut),
        Notification(ctx, message="Please respond", action_data={ATTR_ACTIONS: actions}),
        data={"telegram_chat_id": "123456789"},
    )
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    keyboard = service_data.get("inline_keyboard")
    assert keyboard is not None
    assert len(keyboard) > 0


async def test_deliver_single_action_button() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    actions = [{"title": "Open", "action": "open"}]
    e = Envelope(
        Delivery("telegram_test", ctx.delivery_config("telegram_test"), uut),
        Notification(ctx, message="Single button", action_data={ATTR_ACTIONS: actions}),
        data={"telegram_chat_id": "123456789"},
    )
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    keyboard = service_data.get("inline_keyboard")
    assert keyboard is not None


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


async def test_deliver_missing_chat_id() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    # No chat_id in data and no delivery target configured
    e = _envelope(ctx, message="No target", chat_id=None)
    result = await uut.deliver(e)

    assert result is False
    mock_api.call_service.assert_not_called()


async def test_deliver_service_call_exception() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    mock_api.call_service.side_effect = Exception("Connection timeout")
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Will fail")
    result = await uut.deliver(e)

    assert result is False
    assert len(e.failed_calls) > 0


async def test_deliver_invalid_parse_mode() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Invalid mode", data={"telegram_parse_mode": "InvalidMode"})
    result = await uut.deliver(e)

    # Invalid parse_mode falls back to plain_text; delivery still succeeds
    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data.get("parse_mode") == "plain_text"


async def test_deliver_empty_message() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message=""))

    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Data isolation & security
# ---------------------------------------------------------------------------


async def test_deliver_telegram_keys_not_passed_to_service() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(
        ctx,
        message="Security check",
        data={
            "telegram_parse_mode": "HTML",
            "telegram_disable_notification": True,
            "telegram_chat_id": "987654321",
            "generic_key": "generic_value",
        },
        chat_id=None,  # rely solely on telegram_chat_id in data
    )
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "telegram_parse_mode" not in service_data
    assert "telegram_disable_notification" not in service_data
    assert "telegram_chat_id" not in service_data
    assert "generic_key" in service_data
    assert service_data["generic_key"] == "generic_value"


async def test_deliver_generic_keys_preserved() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Generic data", data={"custom_field": "custom_value", "another_field": 123})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["custom_field"] == "custom_value"
    assert service_data["another_field"] == 123


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "priority",
    [PRIORITY_MINIMUM, PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_CRITICAL],
)
async def test_priority_mapping_all_levels(priority: str) -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message=f"Priority {priority}", priority=priority))

    assert result is True
    assert mock_api.call_service.call_args is not None


# ---------------------------------------------------------------------------
# Edge cases & message handling
# ---------------------------------------------------------------------------


async def test_deliver_very_long_message() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="A" * 5000))

    assert isinstance(result, bool)


async def test_deliver_message_with_special_characters() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Test <b>bold</b> & 'quotes' \"double\" <tag>"))

    assert result is True


async def test_deliver_message_with_unicode() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Hello 世界 🌍 مرحبا мир"))

    assert result is True


async def test_deliver_message_with_newlines() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Line 1\nLine 2\nLine 3"))

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "Line 1" in service_data["message"]


async def test_deliver_none_priority() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Default priority", priority=None))

    assert result is True


async def test_deliver_none_data_dict() -> None:
    """None data dict is handled gracefully; delivery still succeeds with default chat_id."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    # _envelope adds telegram_chat_id by default; pass data=None to confirm no crash
    e = _envelope(ctx, message="No data", data=None)
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "message" in service_data


async def test_deliver_empty_actions_list() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="No actions"))

    assert result is True


# ---------------------------------------------------------------------------
# Service call verification
# ---------------------------------------------------------------------------


async def test_deliver_calls_telegram_bot_service() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Service call test"))

    assert result is True
    call_args = mock_api.call_service.call_args
    assert call_args.args[0] == "telegram_bot"
    assert call_args.args[1] == "send_message"


async def test_deliver_action_data_structure() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    result = await uut.deliver(_envelope(ctx, message="Structure test", title="Title"))

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "message" in service_data
    assert "target" in service_data


# ---------------------------------------------------------------------------
# simplify() text normalization
# ---------------------------------------------------------------------------


def test_simplify_strips_urls() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    result = uut.simplify("Visit https://example.com for more info", strip_urls=True)

    assert result is not None
    assert "https://example.com" not in result


def test_simplify_preserves_urls_by_default() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    result = uut.simplify("Visit https://example.com for more info", strip_urls=False)

    if result:
        assert result.startswith("https://example.com") or "example.com" in result


def test_simplify_none_input() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    result = uut.simplify(None)

    assert result is None or result == ""


# ---------------------------------------------------------------------------
# Transport registration
# ---------------------------------------------------------------------------


def test_transport_name_constant() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    assert uut.name
    assert isinstance(uut.name, str)
    assert len(uut.name) > 0


def test_transport_has_deliver_method() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    assert hasattr(uut, "deliver")
    assert callable(uut.deliver)


# ---------------------------------------------------------------------------
# validate_action
# ---------------------------------------------------------------------------


def test_validate_action_none() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    assert uut.validate_action(None) is False


def test_validate_action_empty_string() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    assert uut.validate_action("") is False


def test_validate_action_unsupported() -> None:
    ctx = _ctx()
    uut = TelegramTransport(ctx)
    assert uut.validate_action("telegram_bot.delete_message") is False


# ---------------------------------------------------------------------------
# _normalise_inline_keyboard / _build_inline_keyboard helpers
# ---------------------------------------------------------------------------


def test_normalise_inline_keyboard_not_a_list() -> None:
    assert _normalise_inline_keyboard("not-a-list") == []  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_normalise_inline_keyboard_ha_native_shape() -> None:
    keyboard = [[["OK", "/ok"], ["Cancel", "/cancel"]]]
    assert _normalise_inline_keyboard(keyboard) == [[["OK", "/ok"], ["Cancel", "/cancel"]]]


def test_normalise_inline_keyboard_telegram_api_dict_shape() -> None:
    keyboard = [[{"text": "OK", "callback_data": "/ok"}]]
    assert _normalise_inline_keyboard(keyboard) == [[["OK", "/ok"]]]


def test_normalise_inline_keyboard_skips_malformed_rows_and_buttons() -> None:
    keyboard = [
        "not-a-row",
        [{"text": "Missing callback"}, {"text": "OK", "callback_data": "/ok"}],
    ]
    assert _normalise_inline_keyboard(keyboard) == [[["OK", "/ok"]]]


async def test_deliver_with_custom_inline_keyboard() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    keyboard = [[{"text": "Yes", "callback_data": "yes"}]]
    e = _envelope(ctx, message="Custom keyboard", data={"telegram_inline_keyboard": keyboard})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["inline_keyboard"] == [[["Yes", "yes"]]]


def test_build_inline_keyboard_no_actions() -> None:
    assert _build_inline_keyboard(None) == []  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    assert _build_inline_keyboard("not-a-list") == []  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_build_inline_keyboard_truncates_to_five_actions() -> None:
    actions = [{"title": f"Action {i}", "action": f"a{i}"} for i in range(7)]
    result = _build_inline_keyboard(actions)
    assert len(result[0]) == 5


def test_build_inline_keyboard_skips_non_dict_action() -> None:
    actions = ["not-a-dict", {"title": "OK", "action": "ok"}]
    result = _build_inline_keyboard(actions)
    assert result == [[["OK", "ok"]]]


def test_build_inline_keyboard_skips_action_missing_title_or_action() -> None:
    actions = [{"title": "No action key"}, {"action": "no_title"}, {"title": "OK", "action": "ok"}]
    result = _build_inline_keyboard(actions)
    assert result == [[["OK", "ok"]]]


def test_build_inline_keyboard_truncates_long_callback_data() -> None:
    long_callback = "x" * 100
    actions = [{"title": "OK", "action": long_callback}]
    result = _build_inline_keyboard(actions)
    callback = result[0][0][1]
    assert len(callback.encode("utf-8")) <= 64


# ---------------------------------------------------------------------------
# Target resolution from envelope.delivery.target
# ---------------------------------------------------------------------------


async def test_deliver_target_from_delivery_target_phone_category() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    delivery = Delivery("telegram_test", {CONF_TARGET: {ATTR_PHONE: ["123456789"]}}, uut)
    e = Envelope(delivery, Notification(ctx, message="Target from delivery"), data=None)
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [123456789]


async def test_deliver_target_from_delivery_target_fallback_category() -> None:
    """When neither phone nor chat_id categories are populated, fall back to any list value."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    delivery = Delivery("telegram_test", {CONF_TARGET: {"custom_category": ["555555555"]}}, uut)
    e = Envelope(delivery, Notification(ctx, message="Fallback target"), data=None)
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [555555555]


async def test_deliver_target_legacy_dict_shape() -> None:
    """Pre-Target-object legacy shape: delivery.target as a bare dict of lists."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Legacy dict target", chat_id=None)
    e.delivery.target = {ATTR_PHONE: ["111222333"]}  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [111222333]


async def test_deliver_target_legacy_dict_shape_scalar_value() -> None:
    """Pre-Target-object legacy shape: delivery.target as a bare dict of scalars."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Legacy scalar dict target", chat_id=None)
    e.delivery.target = {ATTR_PHONE: "777888999"}  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [777888999]


async def test_deliver_target_legacy_list_shape() -> None:
    """Pre-Target-object legacy shape: delivery.target as a bare list."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Legacy list target", chat_id=None)
    e.delivery.target = ["444555666"]  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert service_data["target"] == [444555666]


async def test_deliver_non_numeric_chat_id() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Bad chat id", chat_id="not-a-number")
    result = await uut.deliver(e)

    assert result is False
    mock_api.call_service.assert_not_called()


# ---------------------------------------------------------------------------
# Title + parse_mode combinations
# ---------------------------------------------------------------------------


async def test_deliver_html_parse_mode_with_title_escapes_title() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="body", title="<Alert>", data={"telegram_parse_mode": "HTML"})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "<b>&lt;Alert&gt;</b>" in service_data["message"]


async def test_deliver_markdown_parse_mode_with_title() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="body", title="Alert", data={"telegram_parse_mode": "Markdown"})
    result = await uut.deliver(e)

    assert result is True
    service_data = mock_api.call_service.call_args.kwargs["service_data"]
    assert "*Alert*" in service_data["message"]


# ---------------------------------------------------------------------------
# Image grab failure
# ---------------------------------------------------------------------------


async def test_deliver_grab_image_raises_falls_back_to_text() -> None:
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)
    mock_api = _mock_hass_api()
    uut.hass_api = mock_api

    e = _envelope(ctx, message="Image grab fails", data={"telegram_attach_image": True})
    with patch.object(e, "grab_image", new_callable=AsyncMock, side_effect=RuntimeError("boom")):
        result = await uut.deliver(e)

    assert result is True
    call_args = mock_api.call_service.call_args
    assert call_args.args[1] == "send_message"
    service_data = call_args.kwargs["service_data"]
    assert "file" not in service_data
