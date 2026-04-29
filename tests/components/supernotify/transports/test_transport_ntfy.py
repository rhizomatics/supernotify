"""Test suite for the ntfy transport of SuperNotify.

Coverage:
- _parse_delay(): all supported input formats
- deliver(): happy path, priorities, optional fields
- Priority mapping SuperNotify -> ntfy integer (all 5 levels)
- ntfy_device_id missing -> False without service call
- ntfy_actions truncated to max 3
- ntfy_attach_image: camera_entity_id, snapshot_url, absent
- Graceful fallback if camera.snapshot fails
- ntfy_* keys NOT present in final payload
- ntfy_priority override on automatic mapping
- ntfy_markdown: bool True/False and YAML string "true"/"false" (boolify test)
- target_data uses device_id (not entity_id)
- Service exception -> return False + error_count incremented

Path in upstream repo: tests/components/supernotify/test_transport_ntfy.py
"""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.supernotify.const import (
    ATTR_PRIORITY,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
    TRANSPORT_NTFY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.ntfy import NtfyTransport, _parse_delay
from tests.components.supernotify.hass_setup_lib import TestingContext

# ---------------------------------------------------------------------------
# _parse_delay -- unit tests (no HA dependency)
# ---------------------------------------------------------------------------


def test_parse_delay_minutes() -> None:
    assert _parse_delay("10m") == "00:10"


def test_parse_delay_hours() -> None:
    assert _parse_delay("1h") == "01:00"


def test_parse_delay_hours_and_minutes() -> None:
    assert _parse_delay("2h30m") == "02:30"


def test_parse_delay_seconds_only() -> None:
    assert _parse_delay("30s") == "00:00:30"


def test_parse_delay_hours_minutes_seconds() -> None:
    assert _parse_delay("1h2m3s") == "01:02:03"


def test_parse_delay_hhmm_passthrough() -> None:
    """HH:MM format already correct: returned unchanged."""
    assert _parse_delay("00:10") == "00:10"


def test_parse_delay_hhmmss_passthrough() -> None:
    """HH:MM:SS format already correct: returned unchanged."""
    assert _parse_delay("01:30:00") == "01:30:00"


def test_parse_delay_unknown_format_passthrough() -> None:
    """Unrecognized format: returned unchanged with warning."""
    result = _parse_delay("garbage")
    assert result == "garbage"


def test_parse_delay_empty_string_passthrough() -> None:
    """Empty string: no group matches, returned unchanged."""
    assert _parse_delay("") == ""


# ---------------------------------------------------------------------------
# Helper to build a TestingContext with NtfyTransport
# ---------------------------------------------------------------------------


def _ctx(delivery_data: dict | None = None) -> TestingContext:
    """Create a minimal TestingContext with an ntfy_test delivery."""
    delivery_cfg: dict = {"ntfy_test": {CONF_TRANSPORT: TRANSPORT_NTFY}}
    if delivery_data:
        delivery_cfg["ntfy_test"]["data"] = delivery_data
    return TestingContext(
        deliveries=delivery_cfg,
        transport_types=[NtfyTransport],
    )


def _envelope(
    ctx: TestingContext,
    message: str = "Test",
    title: str | None = None,
    data: dict | None = None,
    media: dict | None = None,
    priority: str | None = None,
) -> Envelope:
    """Build an Envelope ready for deliver()."""
    action_data: dict = {}
    if priority:
        action_data[ATTR_PRIORITY] = priority
    if media:
        action_data["media"] = media

    uut = ctx.transport(TRANSPORT_NTFY)
    return Envelope(
        Delivery("ntfy_test", ctx.delivery_config("ntfy_test"), uut),
        Notification(ctx, message=message, title=title, action_data=action_data or None),
        data=data,
    )


# ---------------------------------------------------------------------------
# deliver() -- happy path
# ---------------------------------------------------------------------------


async def test_deliver_happy_path() -> None:
    """Basic delivery: device_id present -> True, calls ntfy.publish."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    result = await uut.deliver(_envelope(ctx, data={"ntfy_device_id": "abc123"}))

    assert result is True
    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "ntfy",
        "publish",
        service_data={"message": "Test", "priority": 3},
        blocking=False,
        context=None,
        target={"device_id": "abc123"},
        return_response=False,
    )


async def test_deliver_with_title() -> None:
    """Title is included in the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    result = await uut.deliver(_envelope(ctx, message="Body", title="Title", data={"ntfy_device_id": "dev1"}))

    assert result is True
    ctx.hass.services.async_call.assert_called_with(  # type: ignore
        "ntfy",
        "publish",
        service_data={"message": "Body", "title": "Title", "priority": 3},
        blocking=False,
        context=None,
        target={"device_id": "dev1"},
        return_response=False,
    )


# ---------------------------------------------------------------------------
# deliver() -- missing ntfy_device_id
# ---------------------------------------------------------------------------


async def test_deliver_missing_device_id_returns_false() -> None:
    """Without ntfy_device_id -> False, no service call."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    result = await uut.deliver(_envelope(ctx))

    assert result is False
    ctx.hass.services.async_call.assert_not_called()  # type: ignore


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sn_priority", "expected_ntfy_priority"),
    [
        (PRIORITY_CRITICAL, 5),
        (PRIORITY_HIGH, 4),
        (PRIORITY_MEDIUM, 3),
        (PRIORITY_LOW, 2),
        (PRIORITY_MINIMUM, 1),
    ],
)
async def test_priority_mapping(sn_priority: str, expected_ntfy_priority: int) -> None:
    """Each SuperNotify level is mapped to the correct ntfy integer."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1"}, priority=sn_priority)
    await uut.deliver(e)

    assert e.calls, "There must be at least one recorded call"
    assert e.calls[0].action_data
    assert e.calls[0].action_data["priority"] == expected_ntfy_priority


async def test_ntfy_priority_overrides_sn_mapping() -> None:
    """Explicit ntfy_priority overrides the automatic SuperNotify mapping."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_priority": 1},
        priority=PRIORITY_CRITICAL,  # would map to 5, but must be overridden
    )
    await uut.deliver(e)
    assert e.calls[0].action_data
    assert e.calls[0].action_data["priority"] == 1


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


async def test_deliver_with_all_optional_fields() -> None:
    """tags, click, icon, markdown, sequence_id, email are included in payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={
            "ntfy_device_id": "dev1",
            "ntfy_tags": ["warning", "house"],
            "ntfy_click": "https://homeassistant.local:8123",
            "ntfy_icon": "https://example.com/icon.png",
            "ntfy_markdown": True,
            "ntfy_sequence_id": "seq-001",
            "ntfy_email": "user@example.com",
        },
    )
    await uut.deliver(e)

    assert e.calls[0].action_data
    ad = e.calls[0].action_data
    assert ad["tags"] == ["warning", "house"]
    assert ad["click"] == "https://homeassistant.local:8123"
    assert ad["icon"] == "https://example.com/icon.png"
    assert ad["markdown"] is True
    assert ad["sequence_id"] == "seq-001"
    assert ad["email"] == "user@example.com"


async def test_deliver_with_delay() -> None:
    """ntfy_delay '10m' is converted to '00:10' (HH:MM format)."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_delay": "10m"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert e.calls[0].action_data["delay"] == "00:10"


async def test_deliver_with_delay_hours_minutes() -> None:
    """ntfy_delay '1h30m' is converted to '01:30'."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_delay": "1h30m"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert e.calls[0].action_data["delay"] == "01:30"


# ---------------------------------------------------------------------------
# ntfy_actions
# ---------------------------------------------------------------------------


async def test_actions_truncated_to_3() -> None:
    """5 actions provided -> only the first 3 passed to ntfy."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    five_actions = [{"action": "view", "label": f"Link {i}", "url": f"https://example.com/{i}"} for i in range(5)]
    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_actions": five_actions})
    await uut.deliver(e)

    assert e.calls[0].action_data
    actions_sent = e.calls[0].action_data["actions"]
    assert len(actions_sent) == 3
    assert actions_sent[0]["label"] == "Link 0"
    assert actions_sent[2]["label"] == "Link 2"


async def test_actions_exactly_3_not_truncated() -> None:
    """Exactly 3 actions: all 3 passed, no truncation."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    three_actions = [{"action": "view", "label": f"Link {i}", "url": f"https://example.com/{i}"} for i in range(3)]
    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_actions": three_actions})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert len(e.calls[0].action_data["actions"]) == 3


async def test_empty_actions_not_in_payload() -> None:
    """Empty actions list -> 'actions' key absent from payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert "actions" not in e.calls[0].action_data


# ---------------------------------------------------------------------------
# ntfy_* keys must not leak to payload
# ---------------------------------------------------------------------------


async def test_ntfy_keys_not_leaked_to_service_payload() -> None:
    """No key with ntfy_* prefix should appear in the service payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={
            "ntfy_device_id": "dev1",
            "ntfy_tags": ["test"],
            "ntfy_click": "https://example.com",
            "ntfy_markdown": True,
            "ntfy_icon": "https://example.com/icon.png",
            "ntfy_sequence_id": "seq-1",
            "ntfy_email": "test@test.com",
            "ntfy_filename": "photo.jpg",
        },
    )
    await uut.deliver(e)

    assert e.calls[0].action_data
    ad = e.calls[0].action_data
    leaked = [k for k in ad if k.startswith("ntfy_")]
    assert leaked == [], f"ntfy_* keys found in payload: {leaked}"


# ---------------------------------------------------------------------------
# target_data
# ---------------------------------------------------------------------------


async def test_target_data_uses_device_id() -> None:
    """Target is passed as {device_id: ...}, not entity_id."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "abc123def456"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert e.calls[0].target_data == {"device_id": "abc123def456"}


# ---------------------------------------------------------------------------
# ntfy_attach_image
# ---------------------------------------------------------------------------


async def test_attach_image_with_snapshot_url() -> None:
    """ntfy_attach_image=True + snapshot_url -> 'attach' present in payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_attach_image": True, "ntfy_filename": "ingresso.jpg"},
        media={"snapshot_url": "/api/camera_proxy/camera.ingresso"},
    )
    await uut.deliver(e)

    assert e.calls[0].action_data
    ad = e.calls[0].action_data
    assert "attach" in ad
    assert ad.get("filename") == "ingresso.jpg"


async def test_attach_image_false_no_attach() -> None:
    """ntfy_attach_image=False -> grab_image not called, 'attach' absent."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_attach_image": False},
        media={"camera_entity_id": "camera.ingresso"},
    )
    with patch.object(e, "grab_image", new_callable=AsyncMock) as mock_grab:
        await uut.deliver(e)
        mock_grab.assert_not_called()

    assert e.calls[0].action_data
    assert "attach" not in e.calls[0].action_data


async def test_attach_image_true_without_media_no_attach() -> None:
    """ntfy_attach_image=True but no media -> 'attach' absent from payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_attach_image": True})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert "attach" not in e.calls[0].action_data


async def test_attach_image_with_camera_entity_calls_grab_image() -> None:
    """ntfy_attach_image=True + camera_entity_id -> grab_image called, attach in payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_attach_image": True},
        media={"camera_entity_id": "camera.ingresso"},
    )

    assert ctx.media_storage.media_path is not None
    fake_path = ctx.media_storage.media_path / "image/test.jpg"
    with patch.object(e, "grab_image", new_callable=AsyncMock, return_value=fake_path) as mock_grab:
        await uut.deliver(e)
        mock_grab.assert_called_once()

    assert e.calls[0].action_data
    assert "attach" in e.calls[0].action_data
    assert e.calls[0].action_data["attach"].endswith("/supernotify/media/image/test.jpg")


async def test_attach_image_camera_snapshot_failure_delivery_continues() -> None:
    """If camera.snapshot fails, the notification is still sent without attachment."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    async def _side_effect(domain: str, service: str, **kwargs):  # type: ignore[return]
        if domain == "camera" and service == "snapshot":
            raise Exception("camera unreachable")
        return

    ctx.hass.services.async_call.side_effect = _side_effect  # type: ignore

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_attach_image": True},
        media={"camera_entity_id": "camera.ingresso"},
    )
    result = await uut.deliver(e)

    # Notification must still be delivered
    assert result is True

    all_calls = ctx.hass.services.async_call.call_args_list  # type: ignore
    ntfy_calls = [c for c in all_calls if c[0][0] == "ntfy"]
    assert len(ntfy_calls) == 1, "ntfy.publish must be called even after snapshot error"
    assert "attach" not in ntfy_calls[0][1]["service_data"], "'attach' present despite snapshot error"


# ---------------------------------------------------------------------------
# boolify -- correct behavior with YAML strings
# ---------------------------------------------------------------------------


async def test_ntfy_markdown_bool_true_works() -> None:
    """ntfy_markdown=True (Python bool) -> markdown included in payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_markdown": True})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert e.calls[0].action_data.get("markdown") is True


async def test_ntfy_markdown_bool_false_excluded() -> None:
    """ntfy_markdown=False (Python bool) -> markdown NOT included in payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_markdown": False})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert "markdown" not in e.calls[0].action_data


async def test_ntfy_markdown_string_true_is_truthy() -> None:
    """ntfy_markdown='true' (YAML string) -> boolify() converts to True -> markdown included."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_markdown": "true"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert e.calls[0].action_data.get("markdown") is True


async def test_ntfy_markdown_string_false_correctly_handled() -> None:
    """ntfy_markdown='false' (YAML string) -> boolify() converts to False -> markdown excluded.

    This verifies the boolify() fix: without it, bool('false') == True in Python.
    """
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(ctx, data={"ntfy_device_id": "dev1", "ntfy_markdown": "false"})
    await uut.deliver(e)

    assert e.calls[0].action_data
    assert "markdown" not in e.calls[0].action_data


async def test_ntfy_attach_image_string_false_correctly_handled() -> None:
    """ntfy_attach_image='false' (YAML string) -> boolify() converts to False -> grab_image not called.

    This verifies the boolify() fix: without it, bool('false') == True in Python.
    """
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    e = _envelope(
        ctx,
        data={"ntfy_device_id": "dev1", "ntfy_attach_image": "false"},
        media={"camera_entity_id": "camera.test"},
    )
    with patch.object(e, "grab_image", new_callable=AsyncMock) as mock_grab:
        await uut.deliver(e)
        mock_grab.assert_not_called()

    assert e.calls[0].action_data
    assert "attach" not in e.calls[0].action_data


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


async def test_deliver_service_exception_returns_false() -> None:
    """Exception from ntfy.publish -> return False, error_count > 0."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NTFY)

    ctx.hass.services.async_call.side_effect = Exception("Connection refused")  # type: ignore

    e = _envelope(ctx, data={"ntfy_device_id": "dev1"})
    result = await uut.deliver(e)

    assert result is False
    assert e.error_count > 0
