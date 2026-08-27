"""Tests for the Discord transport.

Target file: custom_components/supernotify/transports/discord.py

Coverage:
- TransportFeature flags, default_config, validate_action (any notify.*
  slug accepted), transport name
- Numeric channel/user ID target filtering (select_channels): non-numeric
  dropped with debug log, dedupe, empty -> False + record_error
- deliver(): happy path, title composed as **title** + newline + message,
  title NOT composed when discord_embed has its own title (composed when
  the embed lacks one), priority prefix emoji (opt-in, all 5 priorities,
  default off), embed passthrough (dict only), attach_image (grab_image
  mocked: path / None / exception), image URLs passthrough (list and
  single string), verify_ssl passthrough only when set, exact payload
  shape (whitelist-only data sub-dict, no residual passthrough, data key
  omitted when empty), message truncation at 2000 chars, call_action
  failure, boolify on YAML string bools, force_resend/spoken_message not
  popped and envelope.data never mutated

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_discord.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.supernotify.model import TargetRequired, TransportFeature
from custom_components.supernotify.transports.discord import (
    _MAX_MESSAGE_LENGTH,
    _PRIORITY_PREFIX,
    DiscordTransport,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

CHANNEL_ID = "123456789012345678"
USER_ID = "987654321098765432"


def _make_transport(call_action_result: bool = True) -> Any:
    """Construct a DiscordTransport with hass_api / context / call_action mocked.

    Returns Any (not DiscordTransport): call_action/record_error below are replaced with
    Mocks, which mypy rejects as assignments to real bound methods on the concrete type.
    """
    transport: Any = DiscordTransport.__new__(DiscordTransport)
    transport.hass_api = MagicMock()
    transport.hass_api.call_service = AsyncMock(return_value=None)
    transport.context = MagicMock()
    transport.call_action = AsyncMock(return_value=call_action_result)
    transport.record_error = MagicMock()
    return transport


def _make_envelope(
    message: str | None = "Test message",
    title: str | None = None,
    data: dict[str, Any] | None = None,
    targets: list[Any] | None = None,
    priority: str | None = "medium",
    grab_image_value: Any = None,
    grab_image_raises: bool = False,
) -> MagicMock:
    """Build a mock Envelope exposing the attributes deliver() consumes."""
    envelope = MagicMock()
    envelope.message = message
    envelope.title = title
    envelope.data = data if data is not None else {}
    envelope.priority = priority
    envelope.target = MagicMock()
    envelope.target.resolved_targets = MagicMock(return_value=[CHANNEL_ID] if targets is None else targets)
    if grab_image_raises:
        envelope.grab_image = AsyncMock(side_effect=OSError("camera offline"))
    else:
        envelope.grab_image = AsyncMock(return_value=grab_image_value)
    return envelope


def _action_data(transport: Any) -> dict[str, Any]:
    """Return the action_data kwarg of the most recent call_action invocation."""
    return transport.call_action.call_args.kwargs["action_data"]


# ---------------------------------------------------------------------------
# Schema: features, config, action validation
# ---------------------------------------------------------------------------


def test_supported_features() -> None:
    uut = _make_transport()
    features = uut.supported_features
    assert features & TransportFeature.MESSAGE
    assert features & TransportFeature.TITLE
    assert features & TransportFeature.IMAGES
    assert features & TransportFeature.SNAPSHOT_IMAGE
    # Discord notify service has no action buttons and no spoken output
    assert not features & TransportFeature.ACTIONS
    assert not features & TransportFeature.SPOKEN


def test_default_config() -> None:
    uut = _make_transport()
    config = uut.default_config
    assert config.delivery_defaults.action == "notify.discord"
    assert config.delivery_defaults.target_required == TargetRequired.ALWAYS


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("notify.discord", True),
        ("notify.discord_2", True),  # slug depends on the config entry name
        ("notify.my_discord_bot", True),
        ("notify.", False),  # empty service slug
        ("notify", False),  # missing service part
        ("discord.send", False),  # wrong domain
        ("telegram_bot.send_message", False),
        (None, False),
        ("", False),
    ],
)
def test_validate_action(action: str | None, expected: bool) -> None:
    uut = _make_transport()
    assert uut.validate_action(action) is expected


def test_transport_name() -> None:
    assert DiscordTransport.name == "discord"


# ---------------------------------------------------------------------------
# Numeric channel/user ID targets
# ---------------------------------------------------------------------------


def test_select_channels_filters_and_dedupes() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[CHANNEL_ID, "general", USER_ID, CHANNEL_ID, "123abc"])
    assert uut.select_channels(envelope) == [CHANNEL_ID, USER_ID]


def test_select_channels_accepts_int_targets() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[123456789012345678, USER_ID])
    assert uut.select_channels(envelope) == ["123456789012345678", USER_ID]


def test_select_channels_strips_whitespace() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[f"  {CHANNEL_ID}  "])
    assert uut.select_channels(envelope) == [CHANNEL_ID]


@pytest.mark.parametrize(
    "target",
    [
        "general",  # channel name, not an ID
        "#general",
        "@user",
        "media_player.living_room",  # HA entity
        "",
        None,
        "-42",  # snowflakes are positive
        "0",
        True,  # str(True) is not numeric
    ],
)
def test_select_channels_invalid_target_skipped(target: Any) -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[target, CHANNEL_ID])
    assert uut.select_channels(envelope) == [CHANNEL_ID]


def test_select_channels_no_target_object() -> None:
    uut = _make_transport()
    envelope = _make_envelope()
    envelope.target = None
    assert uut.select_channels(envelope) == []


# ---------------------------------------------------------------------------
# Happy path delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_basic_text_message() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="Hello from SuperNotify", title=None)

    result = await uut.deliver(envelope)

    assert result is True
    uut.call_action.assert_awaited_once()
    action_data = _action_data(uut)
    assert action_data["message"] == "Hello from SuperNotify"
    assert action_data["target"] == [CHANNEL_ID]
    # No data-worthy keys -> data sub-dict omitted entirely
    assert "data" not in action_data


@pytest.mark.asyncio
async def test_deliver_multi_target() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[CHANNEL_ID, USER_ID])

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["target"] == [CHANNEL_ID, USER_ID]


@pytest.mark.asyncio
async def test_deliver_none_message_sends_empty_string() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message=None, title=None)

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["message"] == ""


@pytest.mark.asyncio
async def test_deliver_message_truncated_to_discord_limit() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="x" * (_MAX_MESSAGE_LENGTH + 500))

    result = await uut.deliver(envelope)

    assert result is True
    assert len(_action_data(uut)["message"]) == _MAX_MESSAGE_LENGTH


# ---------------------------------------------------------------------------
# Title composition (Discord markdown, no title field in the service)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_title_composed_as_markdown() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="This is the body", title="Important Alert")

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["message"] == "**Important Alert**\nThis is the body"


@pytest.mark.asyncio
async def test_deliver_title_not_composed_when_embed_has_title() -> None:
    uut = _make_transport()
    embed = {"title": "Embed Title", "description": "embed body", "color": 0xFF0000}
    envelope = _make_envelope(message="plain body", title="Envelope Title", data={"discord_embed": embed})

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    # The embed renders the title, the message body stays plain
    assert action_data["message"] == "plain body"
    assert action_data["data"]["embed"] == embed


@pytest.mark.asyncio
async def test_deliver_title_composed_when_embed_lacks_title() -> None:
    uut = _make_transport()
    embed = {"description": "embed body", "color": 65280}
    envelope = _make_envelope(message="body", title="Title", data={"discord_embed": embed})

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert action_data["message"] == "**Title**\nbody"
    assert action_data["data"]["embed"] == embed


@pytest.mark.asyncio
async def test_deliver_no_title_no_composition() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="just the body", title=None)

    await uut.deliver(envelope)

    assert _action_data(uut)["message"] == "just the body"


# ---------------------------------------------------------------------------
# Priority prefix (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("priority", "expected_prefix"),
    [
        ("critical", _PRIORITY_PREFIX["critical"]),
        ("high", _PRIORITY_PREFIX["high"]),
        ("medium", ""),
        ("low", _PRIORITY_PREFIX["low"]),
        ("minimum", _PRIORITY_PREFIX["minimum"]),
    ],
)
async def test_deliver_priority_prefix_opt_in(priority: str, expected_prefix: str) -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", priority=priority, data={"discord_priority_prefix": True})

    await uut.deliver(envelope)

    assert _action_data(uut)["message"] == f"{expected_prefix}body"


@pytest.mark.asyncio
async def test_deliver_priority_prefix_default_off() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", priority="critical")

    await uut.deliver(envelope)

    assert _action_data(uut)["message"] == "body"


@pytest.mark.asyncio
async def test_deliver_priority_prefix_none_priority_defaults_medium() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", priority=None, data={"discord_priority_prefix": True})

    await uut.deliver(envelope)

    assert _action_data(uut)["message"] == "body"


@pytest.mark.asyncio
async def test_deliver_priority_prefix_applied_before_markdown_title() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title="Title", priority="critical", data={"discord_priority_prefix": True})

    await uut.deliver(envelope)

    expected = _PRIORITY_PREFIX["critical"] + "**Title**\nbody"
    assert _action_data(uut)["message"] == expected


# ---------------------------------------------------------------------------
# Embed passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_embed_passthrough() -> None:
    uut = _make_transport()
    embed = {
        "title": "Alert",
        "description": "Motion detected",
        "color": 16711680,
        "url": "https://ha.local/dashboard",
        "fields": [{"name": "Camera", "value": "Front door"}],
        "footer": {"text": "SuperNotify"},
        "thumbnail": {"url": "https://ha.local/thumb.jpg"},
        "image": {"url": "https://ha.local/image.jpg"},
    }
    envelope = _make_envelope(data={"discord_embed": embed})

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["data"]["embed"] == embed


@pytest.mark.asyncio
async def test_deliver_embed_non_dict_ignored() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title="Title", data={"discord_embed": "not a dict"})

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    assert "data" not in action_data
    # Invalid embed cannot carry a title -> normal markdown composition
    assert action_data["message"].startswith("**Title**\n")


@pytest.mark.asyncio
async def test_deliver_no_embed_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    assert "data" not in _action_data(uut)


# ---------------------------------------------------------------------------
# Image attachment (local snapshot -> data.images)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_attach_image() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"discord_attach_image": True},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    envelope.grab_image.assert_awaited_once()
    assert _action_data(uut)["data"]["images"] == [str(Path("/media/supernotify/snapshot.jpg"))]


@pytest.mark.asyncio
async def test_deliver_attach_image_unavailable() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_attach_image": True}, grab_image_value=None)

    result = await uut.deliver(envelope)

    # Text message still delivered without images key
    assert result is True
    assert "data" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_attach_image_grab_raises() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_attach_image": True}, grab_image_raises=True)

    result = await uut.deliver(envelope)

    assert result is True
    assert "data" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_no_attach_image_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    envelope.grab_image.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("yaml_value", "expect_grab"),
    [
        ("true", True),
        ("false", False),  # bool("false") pitfall: boolify must handle it
        ("on", True),
        ("off", False),
    ],
)
async def test_deliver_attach_image_boolify_yaml_strings(yaml_value: str, expect_grab: bool) -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"discord_attach_image": yaml_value},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    await uut.deliver(envelope)

    assert envelope.grab_image.await_count == (1 if expect_grab else 0)


# ---------------------------------------------------------------------------
# Image URLs (data.urls, allowlist_external_urls downstream)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_image_urls_passthrough() -> None:
    uut = _make_transport()
    urls = ["https://ha.example.org/a.jpg", "https://ha.example.org/b.jpg"]
    envelope = _make_envelope(data={"discord_image_urls": urls})

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["data"]["urls"] == urls


@pytest.mark.asyncio
async def test_deliver_image_urls_single_string_wrapped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_image_urls": "https://ha.example.org/a.jpg"})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"]["urls"] == ["https://ha.example.org/a.jpg"]


@pytest.mark.asyncio
async def test_deliver_image_urls_invalid_type_ignored() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_image_urls": {"url": "nope"}})

    result = await uut.deliver(envelope)

    assert result is True
    assert "data" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_image_urls_empty_entries_dropped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_image_urls": ["", None, "https://ha.example.org/a.jpg"]})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"]["urls"] == ["https://ha.example.org/a.jpg"]


# ---------------------------------------------------------------------------
# verify_ssl
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (False, False),
        (True, True),
        ("false", False),  # YAML string bool via boolify
        ("true", True),
    ],
)
async def test_deliver_verify_ssl_forwarded_when_set(value: Any, expected: bool) -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"discord_verify_ssl": value})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"]["verify_ssl"] is expected


@pytest.mark.asyncio
async def test_deliver_verify_ssl_absent_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    # Not forwarded when unset: the service default (True) applies
    assert "data" not in _action_data(uut)


# ---------------------------------------------------------------------------
# Target error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_no_valid_targets_fails() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=["general", "media_player.tv"])

    result = await uut.deliver(envelope)

    assert result is False
    uut.record_error.assert_called_once()
    uut.call_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_empty_target_list_fails() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[])

    result = await uut.deliver(envelope)

    assert result is False
    uut.record_error.assert_called_once()
    uut.call_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_mixed_targets_only_valid_forwarded() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=["general", CHANNEL_ID, "@user", USER_ID])

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["target"] == [CHANNEL_ID, USER_ID]


# ---------------------------------------------------------------------------
# QUIRK 6: whitelist-only data, no residual passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_no_residual_data_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "discord_verify_ssl": False,
            "generic_key": "generic_value",
            "another_key": 123,
        },
    )

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    service_data = action_data["data"]
    # Whitelist-only sub-dict: no extra keys may leak to the service
    assert set(service_data) <= {"embed", "images", "urls", "verify_ssl"}
    assert "generic_key" not in service_data
    assert "another_key" not in service_data
    assert "generic_key" not in action_data


@pytest.mark.asyncio
async def test_deliver_exact_payload_shape_minimal() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title=None)

    await uut.deliver(envelope)

    assert _action_data(uut) == {
        "message": "body",
        "target": [CHANNEL_ID],
    }


@pytest.mark.asyncio
async def test_deliver_exact_payload_shape_full() -> None:
    uut = _make_transport()
    embed = {"description": "rich"}
    envelope = _make_envelope(
        message="body",
        title=None,
        data={
            "discord_embed": embed,
            "discord_image_urls": ["https://ha.example.org/a.jpg"],
            "discord_verify_ssl": False,
        },
    )

    await uut.deliver(envelope)

    assert _action_data(uut) == {
        "message": "body",
        "target": [CHANNEL_ID],
        "data": {
            "embed": embed,
            "urls": ["https://ha.example.org/a.jpg"],
            "verify_ssl": False,
        },
    }


@pytest.mark.asyncio
async def test_deliver_internal_keys_not_forwarded_and_data_untouched() -> None:
    # force_resend / spoken_message are filtered upstream by notification.py;
    # if they ever reach the envelope they must not leak to the service data,
    # and the transport must not mutate envelope.data
    uut = _make_transport()
    data = {"force_resend": True, "spoken_message": "speak", "discord_verify_ssl": True}
    envelope = _make_envelope(data=data)

    result = await uut.deliver(envelope)

    assert result is True
    service_data = _action_data(uut)["data"]
    assert "force_resend" not in service_data
    assert "spoken_message" not in service_data
    # envelope.data is copied, never mutated by the pops
    assert envelope.data == {"force_resend": True, "spoken_message": "speak", "discord_verify_ssl": True}


@pytest.mark.asyncio
async def test_deliver_discord_keys_not_in_payload() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "discord_embed": {"description": "x"},
            "discord_attach_image": False,
            "discord_image_urls": ["https://ha.example.org/a.jpg"],
            "discord_verify_ssl": True,
            "discord_priority_prefix": True,
        },
    )

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    flat_keys = set(action_data) | set(action_data.get("data", {}))
    assert not any(k.startswith("discord_") for k in flat_keys)


# ---------------------------------------------------------------------------
# Service call failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_call_action_failure_returns_false() -> None:
    uut = _make_transport(call_action_result=False)
    envelope = _make_envelope()

    result = await uut.deliver(envelope)

    assert result is False
    uut.call_action.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_uses_call_action_with_action_data_only() -> None:
    # call_action derives the notify.* service from delivery.action (default
    # notify.discord, or whatever slug the user configured); deliver() must
    # not override it with a qualified_action
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    kwargs = uut.call_action.call_args.kwargs
    assert "action_data" in kwargs
    assert "qualified_action" not in kwargs
