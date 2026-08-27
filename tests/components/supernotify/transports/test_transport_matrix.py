"""Tests for the Matrix transport.

Target file: custom_components/supernotify/transports/matrix.py

Coverage (per design/matrix_design.md):
- TransportFeature flags, default_config, validate_action, transport name
- Room target regex filtering (_MATRIX_ROOM_RE and select_rooms)
- deliver(): happy path text/html, title composition (bold + escape),
  matrix_format override and normalisation, priority prefix (opt-in,
  all 5 priorities, default off), thread_id passthrough, attach_image
  (grab_image mocked: path / None / exception), no valid target ->
  False + record_error, strict schema payload (QUIRK 1: no residual
  data key passthrough, exact payload shape), call_action failure,
  boolify on YAML string bools, force_resend/spoken_message not popped

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_matrix.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.supernotify.model import TargetRequired, TransportFeature
from custom_components.supernotify.transports.matrix import (
    _MATRIX_ROOM_RE,
    _PRIORITY_PREFIX,
    MatrixTransport,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

ROOM_ID = "!abcdef:matrix.org"
ROOM_ALIAS = "#alerts:matrix.org"


def _make_transport(call_action_result: bool = True) -> MatrixTransport:
    """Construct a MatrixTransport with hass_api / context / call_action mocked."""
    transport = MatrixTransport.__new__(MatrixTransport)
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
    targets: list[str] | None = None,
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
    envelope.target.resolved_targets = MagicMock(return_value=[ROOM_ID] if targets is None else targets)
    if grab_image_raises:
        envelope.grab_image = AsyncMock(side_effect=OSError("camera offline"))
    else:
        envelope.grab_image = AsyncMock(return_value=grab_image_value)
    return envelope


def _action_data(transport: MatrixTransport) -> dict[str, Any]:
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
    # Matrix has no action buttons and no spoken output
    assert not features & TransportFeature.ACTIONS
    assert not features & TransportFeature.SPOKEN


def test_default_config() -> None:
    uut = _make_transport()
    config = uut.default_config
    assert config.delivery_defaults.action == "matrix.send_message"
    assert config.delivery_defaults.target_required == TargetRequired.ALWAYS


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("matrix.send_message", True),
        ("matrix.react", False),
        ("notify.matrix_bot", False),
        (None, False),
        ("", False),
    ],
)
def test_validate_action(action: str | None, expected: bool) -> None:
    uut = _make_transport()
    assert uut.validate_action(action) is expected


def test_transport_name() -> None:
    assert MatrixTransport.name == "matrix"


# ---------------------------------------------------------------------------
# Room target regex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "room",
    [
        "!abcdef:matrix.org",
        "#alerts:matrix.org",
        "!x:server",
        "#room-name:home.server.lan",
    ],
)
def test_room_regex_valid(room: str) -> None:
    assert _MATRIX_ROOM_RE.match(room)


@pytest.mark.parametrize(
    "room",
    [
        "room:matrix.org",  # missing sigil
        "!roomnoserver",  # missing server part
        "!room:",  # empty server part
        "@user:matrix.org",  # user ID, not a room
        "media_player.living_room",  # HA entity
        "",
    ],
)
def test_room_regex_invalid(room: str) -> None:
    assert not _MATRIX_ROOM_RE.match(room)


def test_select_rooms_filters_and_dedupes() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[ROOM_ID, "bogus", ROOM_ALIAS, ROOM_ID, "!noserver"])
    assert uut.select_rooms(envelope) == [ROOM_ID, ROOM_ALIAS]


def test_select_rooms_non_string_target_skipped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[12345, None, ROOM_ID])
    assert uut.select_rooms(envelope) == [ROOM_ID]


def test_select_rooms_no_target_object() -> None:
    uut = _make_transport()
    envelope = _make_envelope()
    envelope.target = None
    assert uut.select_rooms(envelope) == []


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
    assert action_data["target"] == [ROOM_ID]
    assert action_data["data"]["format"] == "text"


@pytest.mark.asyncio
async def test_deliver_title_composed_html_bold() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="This is the body", title="Important Alert")

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    # Title present -> default html format, title bolded before the body
    assert action_data["data"]["format"] == "html"
    assert action_data["message"] == "<b>Important Alert</b><br>This is the body"


@pytest.mark.asyncio
async def test_deliver_title_escaped_in_html() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="<i>body kept as-is</i>", title="A <b>& 'raw'</b> title")

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    # Only the title is escaped; the body may contain intentional HTML
    assert action_data["message"].startswith("<b>A &lt;b&gt;&amp; &#x27;raw&#x27;&lt;/b&gt; title</b><br>")
    assert action_data["message"].endswith("<i>body kept as-is</i>")


@pytest.mark.asyncio
async def test_deliver_multi_room() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[ROOM_ID, ROOM_ALIAS])

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["target"] == [ROOM_ID, ROOM_ALIAS]


@pytest.mark.asyncio
async def test_deliver_none_message_sends_empty_string() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message=None, title=None)

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["message"] == ""


# ---------------------------------------------------------------------------
# matrix_format override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_format_text_override_with_title() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title="Title", data={"matrix_format": "text"})

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert action_data["data"]["format"] == "text"
    assert action_data["message"] == "Title\nbody"


@pytest.mark.asyncio
async def test_deliver_format_html_override_without_title() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="<b>rich</b>", title=None, data={"matrix_format": "html"})

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert action_data["data"]["format"] == "html"
    assert action_data["message"] == "<b>rich</b>"


@pytest.mark.asyncio
async def test_deliver_format_normalised_to_lowercase() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"matrix_format": "HTML"})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"]["format"] == "html"


@pytest.mark.asyncio
async def test_deliver_invalid_format_falls_back_to_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title="Title", data={"matrix_format": "markdown"})

    result = await uut.deliver(envelope)

    assert result is True
    # Invalid value ignored: title present -> default html
    assert _action_data(uut)["data"]["format"] == "html"


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
    envelope = _make_envelope(message="body", priority=priority, data={"matrix_priority_prefix": True})

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
    envelope = _make_envelope(message="body", priority=None, data={"matrix_priority_prefix": True})

    await uut.deliver(envelope)

    assert _action_data(uut)["message"] == "body"


@pytest.mark.asyncio
async def test_deliver_priority_prefix_applied_before_html_title() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title="Title", priority="critical", data={"matrix_priority_prefix": True})

    await uut.deliver(envelope)

    expected = _PRIORITY_PREFIX["critical"] + "<b>Title</b><br>body"
    assert _action_data(uut)["message"] == expected


# ---------------------------------------------------------------------------
# thread_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_thread_id_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"matrix_thread_id": "$threadroot:matrix.org"})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"]["thread_id"] == "$threadroot:matrix.org"


@pytest.mark.asyncio
async def test_deliver_thread_id_absent_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    assert "thread_id" not in _action_data(uut)["data"]


# ---------------------------------------------------------------------------
# Image attachment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_attach_image() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"matrix_attach_image": True},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    envelope.grab_image.assert_awaited_once()
    images = _action_data(uut)["data"]["images"]
    assert images == [str(Path("/media/supernotify/snapshot.jpg"))]


@pytest.mark.asyncio
async def test_deliver_attach_image_unavailable() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"matrix_attach_image": True}, grab_image_value=None)

    result = await uut.deliver(envelope)

    # Text message still delivered without images key
    assert result is True
    assert "images" not in _action_data(uut)["data"]


@pytest.mark.asyncio
async def test_deliver_attach_image_grab_raises() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"matrix_attach_image": True}, grab_image_raises=True)

    result = await uut.deliver(envelope)

    assert result is True
    assert "images" not in _action_data(uut)["data"]


@pytest.mark.asyncio
async def test_deliver_no_attach_image_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    envelope.grab_image.assert_not_awaited()
    assert "images" not in _action_data(uut)["data"]


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
        data={"matrix_attach_image": yaml_value},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    await uut.deliver(envelope)

    assert envelope.grab_image.await_count == (1 if expect_grab else 0)


# ---------------------------------------------------------------------------
# Target error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_no_valid_targets_fails() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=["bogus", "media_player.tv"])

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
    envelope = _make_envelope(targets=["bogus", ROOM_ID, "!noserver", ROOM_ALIAS])

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["target"] == [ROOM_ID, ROOM_ALIAS]


# ---------------------------------------------------------------------------
# QUIRK 1: strict service schema, no residual passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_no_residual_data_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "matrix_format": "text",
            "matrix_thread_id": "$t:server",
            "generic_key": "generic_value",
            "another_key": 123,
        },
    )

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    service_data = action_data["data"]
    # Whitelist-only sub-dict: no extra keys may leak to the service
    assert set(service_data) <= {"format", "images", "thread_id"}
    assert "generic_key" not in service_data
    assert "another_key" not in service_data
    assert "generic_key" not in action_data


@pytest.mark.asyncio
async def test_deliver_exact_payload_shape() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title=None)

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert set(action_data) == {"message", "target", "data"}
    assert action_data == {
        "message": "body",
        "target": [ROOM_ID],
        "data": {"format": "text"},
    }


@pytest.mark.asyncio
async def test_deliver_internal_keys_not_forwarded_and_data_untouched() -> None:
    # force_resend / spoken_message are filtered upstream by notification.py;
    # if they ever reach the envelope they must not leak to the strict schema,
    # and the transport must not mutate envelope.data
    uut = _make_transport()
    data = {"force_resend": True, "spoken_message": "speak", "matrix_format": "text"}
    envelope = _make_envelope(data=data)

    result = await uut.deliver(envelope)

    assert result is True
    service_data = _action_data(uut)["data"]
    assert "force_resend" not in service_data
    assert "spoken_message" not in service_data
    # envelope.data is copied, never mutated by the pops
    assert envelope.data == {"force_resend": True, "spoken_message": "speak", "matrix_format": "text"}


@pytest.mark.asyncio
async def test_deliver_matrix_keys_not_in_payload() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "matrix_format": "html",
            "matrix_thread_id": "$t:server",
            "matrix_attach_image": False,
            "matrix_priority_prefix": True,
        },
    )

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    flat_keys = set(action_data) | set(action_data["data"])
    assert not any(k.startswith("matrix_") for k in flat_keys)


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
    # call_action derives matrix.send_message from delivery.action defaults;
    # deliver() must not override it with a qualified_action
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    kwargs = uut.call_action.call_args.kwargs
    assert "action_data" in kwargs
    assert "qualified_action" not in kwargs
