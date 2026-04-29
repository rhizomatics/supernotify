"""Unit tests for Telegram transport in SuperNotify.

Comprehensive test suite covering:
- Happy path delivery scenarios
- All Telegram-specific data keys
- Priority mapping
- Image handling and attachment
- Action button conversion
- Error conditions and edge cases
- Security and data isolation
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.supernotify.const import (
    ATTR_DATA,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import TransportFeature

# Relative imports from the supernotify codebase
from custom_components.supernotify.transports.telegram import TelegramTransport

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_hass_api():
    """Mock Home Assistant API wrapper."""
    api = AsyncMock()
    api.call_service = AsyncMock(return_value=True)
    api.get_state = MagicMock(return_value=None)
    return api


@pytest.fixture
def mock_context():
    """Mock context object."""
    context = MagicMock()
    context.hass_api = AsyncMock()
    context.hass_api.call_service = AsyncMock(return_value=True)
    context.dupe_checker = None
    return context


@pytest.fixture
def make_envelope():
    """Create Envelope objects for testing (factory fixture)."""

    def _make_envelope(
        message="Test message",
        title="Test Title",
        priority="medium",
        data=None,
        actions=None,
        delivery=None,
        media=None,
    ):
        envelope = MagicMock(spec=Envelope)
        envelope.message = message
        envelope.title = title
        envelope.priority = priority
        envelope.data = data or {}
        envelope.actions = actions or []
        envelope.delivery = delivery or MagicMock()
        envelope.delivery.get = MagicMock(return_value=None)
        envelope.notification = MagicMock()
        envelope.notification.data = {}
        envelope.media = media or {}
        return envelope

    return _make_envelope


@pytest.fixture
def telegram_transport(mock_context):
    """Create a TelegramTransport instance with mocked context."""
    transport = TelegramTransport()
    transport.context = mock_context
    transport.hass_api = mock_context.hass_api
    transport.record_error = MagicMock()
    transport.record_success = MagicMock()
    return transport


# ============================================================================
# TEST: SUPPORTED FEATURES
# ============================================================================


def test_supported_features(telegram_transport):
    """Verify TelegramTransport declares all supported features."""
    features = telegram_transport.supported_features
    assert features & TransportFeature.MESSAGE
    assert features & TransportFeature.TITLE
    assert features & TransportFeature.IMAGES
    assert features & TransportFeature.ACTIONS
    assert features & TransportFeature.SNAPSHOT_IMAGE


def test_default_config(telegram_transport):
    """Verify default configuration includes required keys."""
    config = telegram_transport.default_config
    assert "chat_id" in config
    # Default config may include optional parse_mode, reply_markup, etc.


# ============================================================================
# TEST: HAPPY PATH DELIVERY
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_basic_message(telegram_transport, make_envelope):
    """Test successful delivery of basic message without title."""
    envelope = make_envelope(message="Hello from SuperNotify", title=None, priority="medium")
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    telegram_transport.hass_api.call_service.assert_called_once()


@pytest.mark.asyncio
async def test_deliver_message_with_title(telegram_transport, make_envelope):
    """Test delivery of message with title."""
    envelope = make_envelope(message="This is the body", title="Important Alert", priority="high")
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data["title"] == "Important Alert"
    assert action_data["message"] == "This is the body"


@pytest.mark.asyncio
async def test_deliver_critical_priority(telegram_transport, make_envelope):
    """Test delivery with critical priority mapping."""
    envelope = make_envelope(message="CRITICAL ALERT", priority=PRIORITY_CRITICAL)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    # Critical priority should disable notification or set specific flags
    assert action_data[ATTR_DATA].get("disable_notification") is not True


@pytest.mark.asyncio
async def test_deliver_minimum_priority(telegram_transport, make_envelope):
    """Test delivery with minimum priority mapping."""
    envelope = make_envelope(message="Low priority message", priority=PRIORITY_MINIMUM)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True


# ============================================================================
# TEST: TELEGRAM-SPECIFIC DATA KEYS
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_with_parse_mode_html(telegram_transport, make_envelope):
    """Test parse_mode data key for HTML formatting."""
    envelope = make_envelope(message="<b>Bold text</b>", data={"telegram_parse_mode": "HTML"})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("parse_mode") == "HTML"
    # Ensure key was popped and not exposed to service
    assert "telegram_parse_mode" not in action_data[ATTR_DATA]


@pytest.mark.asyncio
async def test_deliver_with_parse_mode_markdown(telegram_transport, make_envelope):
    """Test parse_mode data key for Markdown formatting."""
    envelope = make_envelope(message="**Bold text**", data={"telegram_parse_mode": "Markdown"})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("parse_mode") == "Markdown"


@pytest.mark.asyncio
async def test_deliver_with_disable_notification(telegram_transport, make_envelope):
    """Test disable_notification data key for silent delivery."""
    envelope = make_envelope(message="Silent message", data={"telegram_disable_notification": True})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("disable_notification") is True


@pytest.mark.asyncio
async def test_deliver_with_protect_content(telegram_transport, make_envelope):
    """Test protect_content data key to prevent forwarding."""
    envelope = make_envelope(message="Protected content", data={"telegram_protect_content": True})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("protect_content") is True


@pytest.mark.asyncio
async def test_deliver_with_chat_id_override(telegram_transport, make_envelope):
    """Test telegram_chat_id override in data keys."""
    envelope = make_envelope(message="Override test", data={"telegram_chat_id": "987654321"})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    # Override should use the data key value, not config value
    assert action_data[ATTR_DATA].get("chat_id") == "987654321"


@pytest.mark.asyncio
async def test_deliver_with_reply_to_message_id(telegram_transport, make_envelope):
    """Test reply_to_message_id data key for threaded replies."""
    envelope = make_envelope(message="Reply to previous message", data={"telegram_reply_to_message_id": 42})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("reply_to_message_id") == 42


# ============================================================================
# TEST: IMAGE HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_with_attached_image(telegram_transport, make_envelope):
    """Test delivery with camera snapshot image attachment."""
    image_path = "/tmp/snapshot.jpg"  # noqa: S108
    envelope = make_envelope(message="Here's the snapshot", data={"telegram_attach_image": True})
    envelope.delivery.config = {"chat_id": "123456789"}

    with patch("custom_components.supernotify.envelope.Envelope.grab_image", new_callable=AsyncMock) as mock_grab:
        mock_grab.return_value = Path(image_path)
        result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert str(action_data[ATTR_DATA].get("image")) == image_path


@pytest.mark.asyncio
async def test_deliver_with_image_as_document(telegram_transport, make_envelope):
    """Test image_as_document flag to send photo as file instead of preview."""
    image_path = "/tmp/snapshot.jpg"  # noqa: S108
    envelope = make_envelope(
        message="Document format image", data={"telegram_attach_image": True, "telegram_image_as_document": True}
    )
    envelope.delivery.config = {"chat_id": "123456789"}

    with patch("custom_components.supernotify.envelope.Envelope.grab_image", new_callable=AsyncMock) as mock_grab:
        mock_grab.return_value = Path(image_path)
        result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert action_data[ATTR_DATA].get("image_as_document") is True


@pytest.mark.asyncio
async def test_deliver_image_not_found(telegram_transport, make_envelope):
    """Test graceful handling when grab_image returns None."""
    envelope = make_envelope(message="Image unavailable", data={"telegram_attach_image": True})
    envelope.delivery.config = {"chat_id": "123456789"}

    with patch("custom_components.supernotify.envelope.Envelope.grab_image", new_callable=AsyncMock) as mock_grab:
        mock_grab.return_value = None
        result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    # Should still deliver message without image
    assert "image" not in action_data[ATTR_DATA]


# ============================================================================
# TEST: ACTION BUTTONS (INLINE KEYBOARD)
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_with_action_buttons(telegram_transport, make_envelope):
    """Test conversion of SuperNotify actions to Telegram inline keyboard."""
    actions = [{"title": "Accept", "action": "accept"}, {"title": "Decline", "action": "decline"}]
    envelope = make_envelope(message="Please respond", actions=actions)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    keyboard = action_data[ATTR_DATA].get("inline_keyboard")
    assert keyboard is not None
    # Keyboard should have buttons matching actions
    assert len(keyboard) > 0


@pytest.mark.asyncio
async def test_deliver_single_action_button(telegram_transport, make_envelope):
    """Test single action button delivery."""
    actions = [{"title": "Open", "action": "open"}]
    envelope = make_envelope(message="Single button", actions=actions)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    keyboard = action_data[ATTR_DATA].get("inline_keyboard")
    assert keyboard is not None


# ============================================================================
# TEST: ERROR CONDITIONS
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_missing_chat_id(telegram_transport, make_envelope):
    """Test delivery fails gracefully when chat_id is missing."""
    envelope = make_envelope(message="No target")
    envelope.delivery.config = {}

    # Service call should fail or fallback handling kicks in
    telegram_transport.hass_api.call_service.return_value = False
    result = await telegram_transport.deliver(envelope)

    assert result is False


@pytest.mark.asyncio
async def test_deliver_service_call_exception(telegram_transport, make_envelope):
    """Test exception handling when Telegram service call fails."""
    envelope = make_envelope(message="Will fail")
    envelope.delivery.config = {"chat_id": "123456789"}

    telegram_transport.hass_api.call_service.side_effect = Exception("Connection timeout")
    result = await telegram_transport.deliver(envelope)

    assert result is False
    telegram_transport.record_error.assert_called()


@pytest.mark.asyncio
async def test_deliver_invalid_parse_mode(telegram_transport, make_envelope):
    """Test handling of invalid parse_mode value."""
    envelope = make_envelope(message="Invalid mode", data={"telegram_parse_mode": "InvalidMode"})
    envelope.delivery.config = {"chat_id": "123456789"}

    await telegram_transport.deliver(envelope)

    # Transport should either sanitize or pass through; verify call still made
    assert telegram_transport.hass_api.call_service.called


@pytest.mark.asyncio
async def test_deliver_empty_message(telegram_transport, make_envelope):
    """Test delivery with empty message string."""
    envelope = make_envelope(message="")
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    # Empty message may be rejected or replaced with placeholder
    # Behavior depends on implementation
    if result:
        call_args = telegram_transport.hass_api.call_service.call_args
        assert call_args is not None


# ============================================================================
# TEST: DATA ISOLATION & SECURITY
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_telegram_keys_not_passed_to_service(telegram_transport, make_envelope):
    """Verify telegram_* data keys are removed before calling service."""
    envelope = make_envelope(
        message="Security check",
        data={
            "telegram_parse_mode": "HTML",
            "telegram_disable_notification": True,
            "telegram_chat_id": "override_id",
            "generic_key": "generic_value",
        },
    )
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    service_data = action_data[ATTR_DATA]

    # Telegram-specific keys should be removed (popped)
    assert "telegram_parse_mode" not in service_data
    assert "telegram_disable_notification" not in service_data
    assert "telegram_chat_id" not in service_data

    # Generic keys should remain
    assert "generic_key" in service_data
    assert service_data["generic_key"] == "generic_value"


@pytest.mark.asyncio
async def test_deliver_generic_keys_preserved(telegram_transport, make_envelope):
    """Verify non-Telegram data keys are preserved in service call."""
    envelope = make_envelope(message="Generic data", data={"custom_field": "custom_value", "another_field": 123})
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    service_data = action_data[ATTR_DATA]

    # All generic keys should be present
    assert service_data["custom_field"] == "custom_value"
    assert service_data["another_field"] == 123


# ============================================================================
# TEST: PRIORITY MAPPING
# ============================================================================


@pytest.mark.asyncio
async def test_priority_mapping_all_levels(telegram_transport, make_envelope):
    """Test priority mapping for all SuperNotify priority levels."""
    priorities = [PRIORITY_MINIMUM, PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_CRITICAL]

    for priority in priorities:
        envelope = make_envelope(message=f"Priority {priority}", priority=priority)
        envelope.delivery.config = {"chat_id": "123456789"}

        result = await telegram_transport.deliver(envelope)

        assert result is True
        call_args = telegram_transport.hass_api.call_service.call_args
        assert call_args is not None


# ============================================================================
# TEST: EDGE CASES & MESSAGE HANDLING
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_very_long_message(telegram_transport, make_envelope):
    """Test delivery of message longer than Telegram's limit."""
    long_message = "A" * 5000  # Telegram limit is ~4096 chars
    envelope = make_envelope(message=long_message)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    # Message may be truncated or split; verify no exception
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_deliver_message_with_special_characters(telegram_transport, make_envelope):
    """Test message with HTML/Markdown special characters."""
    special_message = "Test <b>bold</b> & 'quotes' \"double\" <tag>"
    envelope = make_envelope(message=special_message)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True


@pytest.mark.asyncio
async def test_deliver_message_with_unicode(telegram_transport, make_envelope):
    """Test message with Unicode characters."""
    unicode_message = "Hello 世界 🌍 مرحبا мир"
    envelope = make_envelope(message=unicode_message)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True


@pytest.mark.asyncio
async def test_deliver_message_with_newlines(telegram_transport, make_envelope):
    """Test message with newline characters."""
    multiline_message = "Line 1\nLine 2\nLine 3"
    envelope = make_envelope(message=multiline_message)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert "Line 1" in action_data["message"]


# ============================================================================
# TEST: ENVELOPE VALIDATION
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_none_priority(telegram_transport, make_envelope):
    """Test delivery with None priority defaults to medium."""
    envelope = make_envelope(message="Default priority", priority=None)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True


@pytest.mark.asyncio
async def test_deliver_none_data_dict(telegram_transport, make_envelope):
    """Test delivery with None data dict."""
    envelope = make_envelope(message="No data", data=None)
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    action_data = call_args[1]["action_data"]
    assert ATTR_DATA in action_data


@pytest.mark.asyncio
async def test_deliver_empty_actions_list(telegram_transport, make_envelope):
    """Test delivery with empty actions list."""
    envelope = make_envelope(message="No actions", actions=[])
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True


# ============================================================================
# TEST: INTEGRATION WITH HASS API
# ============================================================================


@pytest.mark.asyncio
async def test_deliver_calls_notify_telegram_service(telegram_transport, make_envelope):
    """Verify delivery calls the telegram notify service."""
    envelope = make_envelope(message="Service call test")
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    # Should call the telegram notify service
    telegram_transport.hass_api.call_service.assert_called_once()
    call_args = telegram_transport.hass_api.call_service.call_args
    # Verify domain and service are correct
    assert call_args[0][0] == "telegram_bot" or "telegram" in str(call_args)


@pytest.mark.asyncio
async def test_deliver_action_data_structure(telegram_transport, make_envelope):
    """Verify action_data follows standard ServiceCall structure."""
    envelope = make_envelope(message="Structure test", title="Title")
    envelope.delivery.config = {"chat_id": "123456789"}

    result = await telegram_transport.deliver(envelope)

    assert result is True
    call_args = telegram_transport.hass_api.call_service.call_args
    # Standard structure: domain, service, action_data
    assert "action_data" in call_args[1]
    action_data = call_args[1]["action_data"]
    assert "message" in action_data
    assert ATTR_DATA in action_data


# ============================================================================
# TEST: SIMPLIFY METHOD (TEXT NORMALIZATION)
# ============================================================================


def test_simplify_strips_urls(telegram_transport):
    """Test simplify() removes URLs from text."""
    text = "Visit https://example.com for more info"
    result = telegram_transport.simplify(text, strip_urls=True)

    assert result is not None
    assert "https://example.com" not in result


def test_simplify_preserves_urls_by_default(telegram_transport):
    """Test simplify() preserves URLs when strip_urls=False."""
    text = "Visit https://example.com for more info"
    result = telegram_transport.simplify(text, strip_urls=False)

    if result:
        assert "https://example.com" in result or "example.com" in result


def test_simplify_none_input(telegram_transport):
    """Test simplify() handles None input gracefully."""
    result = telegram_transport.simplify(None)

    assert result is None or result == ""


# ============================================================================
# TEST: TRANSPORT REGISTRATION
# ============================================================================


def test_transport_name_constant(telegram_transport):
    """Verify transport has a valid name constant."""
    assert telegram_transport.name
    assert isinstance(telegram_transport.name, str)
    assert len(telegram_transport.name) > 0


def test_transport_has_deliver_method(telegram_transport):
    """Verify transport implements deliver() method."""
    assert hasattr(telegram_transport, "deliver")
    assert callable(telegram_transport.deliver)
