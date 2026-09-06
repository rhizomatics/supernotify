"""Tests for the HTML5 browser push transport.

Target file: custom_components/supernotify/transports/html5.py

Coverage:
- TransportFeature flags, default_config, validate_action, transport name
- Target filtering (notify.* entity prefix, dedupe, empty -> False +
  record_error)
- deliver(): happy path, required title fallback "Home Assistant",
  urgency mapping for all 5 priorities, html5_urgency override
  (valid / invalid / case normalisation), tag / actions / vibrate / ttl
  passthrough, html5_url and html5_data merge into the custom data field,
  attach_image (snapshot URL from media > grab_image + object_url >
  none), exact whitelist payload shape (no residual data key
  passthrough), boolify on YAML string bools, call_action failure,
  force_resend/spoken_message not popped, envelope.data never mutated

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_html5.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.supernotify.model import TargetRequired, TransportFeature
from custom_components.supernotify.transports.html5 import (
    _HTML5_TARGET_RE,
    _URGENCY_BY_PRIORITY,
    HTML5Transport,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

BROWSER_1 = "notify.chrome_lollo"
BROWSER_2 = "notify.firefox_desk"

SNAPSHOT_REL_URL = "/media/supernotify/snapshot.jpg"
SNAPSHOT_ABS_URL = "https://ha.example.com/media/supernotify/snapshot.jpg"
OBJECT_URL = "https://ha.example.com/supernotify/media/processed.jpg"


def _make_transport(call_action_result: bool = True) -> Any:  # ruff: ignore[any-type]
    """Construct an HTML5Transport with hass_api / context / call_action mocked.

    Returns Any (not HTML5Transport): call_action/record_error below are replaced with
    Mocks, which mypy and ty reject as assignments to real bound methods on the concrete type.
    """
    transport: Any = HTML5Transport.__new__(HTML5Transport)
    transport.hass_api = MagicMock()
    transport.hass_api.call_service = AsyncMock(return_value=None)
    transport.hass_api.abs_url = MagicMock(return_value=SNAPSHOT_ABS_URL)
    transport.context = MagicMock()
    transport.context.media_storage.object_url = AsyncMock(return_value=OBJECT_URL)
    transport.call_action = AsyncMock(return_value=call_action_result)
    transport.record_error = MagicMock()
    return transport


def _make_envelope(
    message: str | None = "Test message",
    title: str | None = None,
    data: dict[str, Any] | None = None,
    targets: list[Any] | None = None,
    priority: str | None = "medium",
    media: dict[str, Any] | None = None,
    grab_image_value: Path | None = None,
    grab_image_raises: bool = False,
) -> MagicMock:
    """Build a mock Envelope exposing the attributes deliver() consumes."""
    envelope = MagicMock()
    envelope.message = message
    envelope.title = title
    envelope.data = data if data is not None else {}
    envelope.priority = priority
    envelope.media = media
    envelope.target = MagicMock()
    envelope.target.resolved_targets = MagicMock(return_value=[BROWSER_1] if targets is None else targets)
    if grab_image_raises:
        envelope.grab_image = AsyncMock(side_effect=OSError("camera offline"))
    else:
        envelope.grab_image = AsyncMock(return_value=grab_image_value)
    return envelope


def _action_data(transport: Any) -> dict[str, Any]:  # ruff: ignore[any-type]
    """Return the action_data kwarg of the most recent call_action invocation."""
    return transport.call_action.call_args.kwargs["action_data"]


def _target_data(transport: Any) -> dict[str, Any]:  # ruff: ignore[any-type]
    """Return the target_data kwarg of the most recent call_action invocation."""
    return transport.call_action.call_args.kwargs["target_data"]


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
    assert features & TransportFeature.ACTIONS
    # Browser push has no spoken output
    assert not features & TransportFeature.SPOKEN


def test_default_config() -> None:
    uut = _make_transport()
    config = uut.default_config
    assert config.delivery_defaults.action == "html5.send_message"
    assert config.delivery_defaults.target_required == TargetRequired.ALWAYS


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("html5.send_message", True),
        ("html5.dismiss", False),
        ("notify.html5", False),
        (None, False),
        ("", False),
    ],
)
def test_validate_action(action: str | None, expected: bool) -> None:
    uut = _make_transport()
    assert uut.validate_action(action) is expected


def test_transport_name() -> None:
    assert HTML5Transport.name == "html5"


# ---------------------------------------------------------------------------
# Target filtering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "notify.chrome_lollo",
        "notify.firefox_desk_2",
        "notify.a",
    ],
)
def test_target_regex_valid(target: str) -> None:
    assert _HTML5_TARGET_RE.match(target)


@pytest.mark.parametrize(
    "target",
    [
        "chrome_lollo",  # missing domain
        "media_player.tv",  # wrong domain
        "notify.",  # empty entity name
        "notify.chrome lollo",  # illegal char
        "person.lollo",
        "",
    ],
)
def test_target_regex_invalid(target: str) -> None:
    assert not _HTML5_TARGET_RE.match(target)


def test_select_targets_filters_and_dedupes() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[BROWSER_1, "bogus", BROWSER_2, BROWSER_1, "media_player.tv"])
    assert uut.select_targets(envelope) == [BROWSER_1, BROWSER_2]


def test_select_targets_non_string_skipped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[12345, None, BROWSER_1])
    assert uut.select_targets(envelope) == [BROWSER_1]


def test_select_targets_no_target_object() -> None:
    uut = _make_transport()
    envelope = _make_envelope()
    envelope.target = None
    assert uut.select_targets(envelope) == []


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
async def test_deliver_targets_forwarded_as_entity_ids() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=["bogus", BROWSER_1, BROWSER_2])

    result = await uut.deliver(envelope)

    assert result is True
    assert _target_data(uut) == {"entity_id": [BROWSER_1, BROWSER_2]}


# ---------------------------------------------------------------------------
# Happy path delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_basic_message() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="Hello from SuperNotify", title="Doorbell")

    result = await uut.deliver(envelope)

    assert result is True
    uut.call_action.assert_awaited_once()
    action_data = _action_data(uut)
    assert action_data["title"] == "Doorbell"
    assert action_data["message"] == "Hello from SuperNotify"
    assert action_data["urgency"] == "normal"


@pytest.mark.asyncio
async def test_deliver_uses_call_action_without_qualified_action() -> None:
    # call_action derives html5.send_message from delivery.action defaults;
    # deliver() must not override it with a qualified_action
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    kwargs = uut.call_action.call_args.kwargs
    assert "action_data" in kwargs
    assert "target_data" in kwargs
    assert "qualified_action" not in kwargs


@pytest.mark.asyncio
async def test_deliver_none_message_sends_empty_string() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message=None, title="Title only")

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["message"] == ""


# ---------------------------------------------------------------------------
# Required title fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_title_fallback_when_absent() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title=None)

    await uut.deliver(envelope)

    assert _action_data(uut)["title"] == "Home Assistant"


@pytest.mark.asyncio
async def test_deliver_title_fallback_when_empty() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title="")

    await uut.deliver(envelope)

    assert _action_data(uut)["title"] == "Home Assistant"


@pytest.mark.asyncio
async def test_deliver_envelope_title_preserved() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title="Motion detected")

    await uut.deliver(envelope)

    assert _action_data(uut)["title"] == "Motion detected"


# ---------------------------------------------------------------------------
# Urgency: priority mapping + override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("priority", "expected_urgency"),
    [
        ("critical", "high"),
        ("high", "high"),
        ("medium", "normal"),
        ("low", "low"),
        ("minimum", "low"),
    ],
)
async def test_deliver_urgency_from_priority(priority: str, expected_urgency: str) -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority=priority)

    await uut.deliver(envelope)

    assert _action_data(uut)["urgency"] == expected_urgency


@pytest.mark.asyncio
async def test_deliver_urgency_none_priority_defaults_normal() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority=None)

    await uut.deliver(envelope)

    assert _action_data(uut)["urgency"] == "normal"


@pytest.mark.asyncio
async def test_deliver_urgency_override_valid() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority="critical", data={"html5_urgency": "low"})

    await uut.deliver(envelope)

    assert _action_data(uut)["urgency"] == "low"


@pytest.mark.asyncio
async def test_deliver_urgency_override_normalised_to_lowercase() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority="low", data={"html5_urgency": "HIGH"})

    await uut.deliver(envelope)

    assert _action_data(uut)["urgency"] == "high"


@pytest.mark.asyncio
async def test_deliver_urgency_override_invalid_falls_back_to_priority() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority="critical", data={"html5_urgency": "urgent"})

    result = await uut.deliver(envelope)

    assert result is True
    # Invalid override ignored: critical -> high
    assert _action_data(uut)["urgency"] == "high"


def test_urgency_map_covers_all_priorities() -> None:
    assert set(_URGENCY_BY_PRIORITY) == {"critical", "high", "medium", "low", "minimum"}
    assert set(_URGENCY_BY_PRIORITY.values()) <= {"low", "normal", "high"}


# ---------------------------------------------------------------------------
# First-class field passthrough: tag / actions / vibrate / ttl / icon / badge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_tag_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_tag": "doorbell"})

    await uut.deliver(envelope)

    assert _action_data(uut)["tag"] == "doorbell"


@pytest.mark.asyncio
async def test_deliver_actions_passthrough() -> None:
    uut = _make_transport()
    actions = [
        {"action": "open_door", "title": "Open", "icon": "/local/door.png"},
        {"action": "ignore", "title": "Ignore"},
    ]
    envelope = _make_envelope(data={"html5_actions": actions})

    await uut.deliver(envelope)

    assert _action_data(uut)["actions"] == actions


@pytest.mark.asyncio
async def test_deliver_actions_non_list_dropped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_actions": "open_door"})

    result = await uut.deliver(envelope)

    assert result is True
    assert "actions" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_vibrate_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_vibrate": [200, 100, 200]})

    await uut.deliver(envelope)

    assert _action_data(uut)["vibrate"] == [200, 100, 200]


@pytest.mark.asyncio
async def test_deliver_vibrate_non_list_dropped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_vibrate": 200})

    result = await uut.deliver(envelope)

    assert result is True
    assert "vibrate" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_silent_and_vibrate_mutually_exclusive_silent_wins() -> None:
    # The service schema declares silent/vibrate as vol.Exclusive: sending
    # both keys fails the whole call. A truthy silent wins, vibrate dropped.
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_silent": True, "html5_vibrate": [200, 100, 200]})

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    assert action_data["silent"] is True
    assert "vibrate" not in action_data


@pytest.mark.asyncio
async def test_deliver_silent_and_vibrate_mutually_exclusive_falsy_silent_dropped() -> None:
    # A falsy silent is dropped in favour of the vibrate pattern
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_silent": False, "html5_vibrate": [200, 100, 200]})

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    assert action_data["vibrate"] == [200, 100, 200]
    assert "silent" not in action_data


@pytest.mark.asyncio
async def test_deliver_ttl_int_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_ttl": 86400})

    await uut.deliver(envelope)

    assert _action_data(uut)["ttl"] == 86400


@pytest.mark.asyncio
async def test_deliver_ttl_duration_dict_passthrough() -> None:
    # The service schema uses a duration selector: forward dicts untouched
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_ttl": {"hours": 1, "minutes": 30}})

    await uut.deliver(envelope)

    assert _action_data(uut)["ttl"] == {"hours": 1, "minutes": 30}


@pytest.mark.asyncio
async def test_deliver_icon_and_badge_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"html5_icon": "/local/icon.png", "html5_badge": "/local/badge.png"},
    )

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert action_data["icon"] == "/local/icon.png"
    assert action_data["badge"] == "/local/badge.png"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "field"),
    [
        ("html5_renotify", "renotify"),
        ("html5_silent", "silent"),
        ("html5_require_interaction", "require_interaction"),
    ],
)
async def test_deliver_bool_flags_true(key: str, field: str) -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={key: True})

    await uut.deliver(envelope)

    assert _action_data(uut)[field] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("yaml_value", "expected"),
    [
        ("true", True),
        ("false", False),  # bool("false") pitfall: boolify must handle it
        ("on", True),
        ("off", False),
    ],
)
async def test_deliver_bool_flags_boolify_yaml_strings(yaml_value: str, expected: bool) -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_require_interaction": yaml_value})

    await uut.deliver(envelope)

    assert _action_data(uut)["require_interaction"] is expected


@pytest.mark.asyncio
async def test_deliver_bool_flags_absent_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert "renotify" not in action_data
    assert "silent" not in action_data
    assert "require_interaction" not in action_data


# ---------------------------------------------------------------------------
# Custom data field: html5_url and html5_data merge
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_click_url_in_data_field() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_url": "/lovelace/security"})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"] == {"url": "/lovelace/security"}


@pytest.mark.asyncio
async def test_deliver_custom_data_merge() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_data": {"foo": "bar", "count": 3}})

    await uut.deliver(envelope)

    assert _action_data(uut)["data"] == {"foo": "bar", "count": 3}


@pytest.mark.asyncio
async def test_deliver_url_wins_over_custom_data_url() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "html5_url": "/lovelace/security",
            "html5_data": {"url": "/lovelace/other", "foo": "bar"},
        },
    )

    await uut.deliver(envelope)

    assert _action_data(uut)["data"] == {"url": "/lovelace/security", "foo": "bar"}


@pytest.mark.asyncio
async def test_deliver_custom_data_non_dict_dropped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_data": "not-a-dict"})

    result = await uut.deliver(envelope)

    assert result is True
    assert "data" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_data_field_absent_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    assert "data" not in _action_data(uut)


# ---------------------------------------------------------------------------
# Image attachment (URL pattern, never local paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_attach_image_snapshot_url_preferred() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"html5_attach_image": True},
        media={"snapshot_url": SNAPSHOT_REL_URL},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    uut.hass_api.abs_url.assert_called_once_with(SNAPSHOT_REL_URL)
    assert _action_data(uut)["image"] == SNAPSHOT_ABS_URL
    # snapshot URL wins: no grab_image call at all
    envelope.grab_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_attach_image_fallback_grab_and_object_url() -> None:
    uut = _make_transport()
    image_path = Path("/media/supernotify/snapshot.jpg")
    envelope = _make_envelope(
        data={"html5_attach_image": True},
        media=None,
        grab_image_value=image_path,
    )

    result = await uut.deliver(envelope)

    assert result is True
    envelope.grab_image.assert_awaited_once()
    uut.context.media_storage.object_url.assert_awaited_once_with(image_path)
    assert _action_data(uut)["image"] == OBJECT_URL


@pytest.mark.asyncio
async def test_deliver_attach_image_no_image_available() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_attach_image": True}, media=None, grab_image_value=None)

    result = await uut.deliver(envelope)

    # Message still delivered without an image field
    assert result is True
    assert "image" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_attach_image_object_url_none() -> None:
    uut = _make_transport()
    uut.context.media_storage.object_url = AsyncMock(return_value=None)
    envelope = _make_envelope(
        data={"html5_attach_image": True},
        media=None,
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    assert "image" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_attach_image_grab_raises() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"html5_attach_image": True}, media=None, grab_image_raises=True)

    result = await uut.deliver(envelope)

    assert result is True
    assert "image" not in _action_data(uut)


@pytest.mark.asyncio
async def test_deliver_no_attach_image_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope(media={"snapshot_url": SNAPSHOT_REL_URL})

    await uut.deliver(envelope)

    envelope.grab_image.assert_not_awaited()
    assert "image" not in _action_data(uut)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("yaml_value", "expect_grab"),
    [
        ("true", True),
        ("false", False),
        ("on", True),
        ("off", False),
    ],
)
async def test_deliver_attach_image_boolify_yaml_strings(yaml_value: str, expect_grab: bool) -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"html5_attach_image": yaml_value},
        media=None,
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    await uut.deliver(envelope)

    assert envelope.grab_image.await_count == (1 if expect_grab else 0)


# ---------------------------------------------------------------------------
# Strict whitelist schema: exact payload, no residual passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_exact_payload_shape() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title="Title", priority="high")

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert action_data == {
        "title": "Title",
        "message": "body",
        "urgency": "high",
    }
    assert _target_data(uut) == {"entity_id": [BROWSER_1]}


@pytest.mark.asyncio
async def test_deliver_no_residual_data_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "html5_tag": "doorbell",
            "generic_key": "generic_value",
            "another_key": 123,
        },
    )

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    # Whitelist-only payload: no extra keys may leak to the service
    assert "generic_key" not in action_data
    assert "another_key" not in action_data
    allowed = {
        "title",
        "message",
        "urgency",
        "icon",
        "badge",
        "image",
        "tag",
        "actions",
        "renotify",
        "silent",
        "require_interaction",
        "vibrate",
        "ttl",
        "data",
    }
    assert set(action_data) <= allowed


@pytest.mark.asyncio
async def test_deliver_html5_keys_not_in_payload() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "html5_urgency": "high",
            "html5_tag": "t",
            "html5_url": "/x",
            "html5_attach_image": False,
            "html5_data": {"k": "v"},
        },
    )

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    flat_keys = set(action_data) | set(action_data.get("data", {}))
    assert not any(k.startswith("html5_") for k in flat_keys)


@pytest.mark.asyncio
async def test_deliver_internal_keys_not_forwarded_and_data_untouched() -> None:
    # force_resend / spoken_message are filtered upstream by notification.py;
    # if they ever reach the envelope they must not leak to the strict schema,
    # and the transport must not mutate envelope.data
    uut = _make_transport()
    data = {"force_resend": True, "spoken_message": "speak", "html5_tag": "t"}
    envelope = _make_envelope(data=data)

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    assert "force_resend" not in action_data
    assert "spoken_message" not in action_data
    # envelope.data is copied, never mutated by the pops
    assert envelope.data == {"force_resend": True, "spoken_message": "speak", "html5_tag": "t"}


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
