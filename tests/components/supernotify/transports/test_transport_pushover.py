"""Test suite for the SuperNotify Pushover transport.

Coverage:
- deliver(): happy path, base call without data
- Priority mapping SuperNotify -> Pushover integer (all 5 levels)
- pushover_priority override on the auto-mapping
- pushover_priority: out-of-range -> auto mapping
- pushover_priority: non-numeric value -> auto mapping
- Emergency (priority=2): retry and expire defaults
- Emergency: retry < 30 -> clamping to 30
- Emergency: expire > 10800 -> clamping to 10800
- Emergency: explicit pushover_retry/expire
- Emergency: pushover_callback included
- Optional fields: sound, url, url_title, html, ttl, device
- html=True -> "html": 1 in payload
- pushover_ttl non-numeric -> ignored with warning
- pushover_* keys NOT present in the final payload
- pushover_attach_image=True -> grab_image() called
- pushover_attach_image=True + grab_image None -> no 'attachment'
- pushover_attach_image=False -> 'attachment' absent
- grab_image() raises -> delivery continues without attachment
- validate_action: notify.* valid
- validate_action: non-notify -> False
- service call exception -> return False
- title present in payload
- no extra data (raw_data residue) forwarded to the service

Path in the upstream repo: tests/components/supernotify/transports/test_transport_pushover.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.supernotify.const import (
    ATTR_PRIORITY,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
    TRANSPORT_PUSHOVER,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.pushover import PushoverTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(
    delivery_data: dict | None = None,
    action: str = "notify.pushover_home",
) -> TestingContext:
    """Build a minimal TestingContext with one pushover_test delivery."""
    delivery_cfg: dict = {
        "pushover_test": {
            CONF_TRANSPORT: TRANSPORT_PUSHOVER,
            "action": action,
        }
    }
    if delivery_data:
        delivery_cfg["pushover_test"]["data"] = delivery_data
    return TestingContext(
        deliveries=delivery_cfg,
        transport_types=[PushoverTransport],
    )


def _envelope(
    ctx: TestingContext,
    message: str = "Test",
    title: str | None = None,
    data: dict | None = None,
    priority: str | None = None,
) -> Envelope:
    """Build an Envelope ready for deliver()."""
    action_data: dict = {}
    if priority:
        action_data[ATTR_PRIORITY] = priority

    uut = ctx.transport(TRANSPORT_PUSHOVER)
    return Envelope(
        Delivery("pushover_test", ctx.delivery_config("pushover_test"), uut),
        Notification(ctx, message=message, title=title, action_data=action_data or None),
        data=data,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_deliver_happy_path_no_data() -> None:
    """Base delivery without data: priority=0 (medium), calls notify.pushover_home."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    result = await uut.deliver(_envelope(ctx))

    assert result is True
    ctx.hass.services.async_call.assert_called_once()  # type: ignore
    call_kwargs = ctx.hass.services.async_call.call_args  # type: ignore
    assert call_kwargs[0][0] == "notify"
    assert call_kwargs[0][1] == "pushover_home"
    service_data = call_kwargs[1]["service_data"]
    assert service_data["message"] == "Test"
    assert service_data["data"]["priority"] == 0


async def test_deliver_with_title() -> None:
    """The title is included in the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    result = await uut.deliver(_envelope(ctx, message="Body", title="Title"))

    assert result is True
    service_data = ctx.hass.services.async_call.call_args[1]["service_data"]  # type: ignore
    assert service_data["title"] == "Title"
    assert service_data["message"] == "Body"


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sn_priority", "expected_pushover_priority"),
    [
        (PRIORITY_CRITICAL, 2),
        (PRIORITY_HIGH, 1),
        (PRIORITY_MEDIUM, 0),
        (PRIORITY_LOW, -1),
        (PRIORITY_MINIMUM, -2),
    ],
)
async def test_priority_mapping(sn_priority: str, expected_pushover_priority: int) -> None:
    """Each SuperNotify level maps to the correct Pushover integer."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    # For critical, patch grab_image and the service call to avoid emergency-mode loop
    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(ctx, priority=sn_priority)
        await uut.deliver(e)

    service_data = ctx.hass.services.async_call.call_args[1]["service_data"]  # type: ignore
    assert service_data["data"]["priority"] == expected_pushover_priority


async def test_priority_override_explicit() -> None:
    """Explicit pushover_priority overrides the auto-mapping."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(
        ctx,
        data={"pushover_priority": 1},
        priority=PRIORITY_MINIMUM,  # would map to -2, must be overridden
    )
    await uut.deliver(e)

    assert e.calls[0].action_data["data"]["priority"] == 1  # type: ignore[index]


async def test_priority_override_out_of_range_uses_mapping() -> None:
    """pushover_priority out of range (-2..2) -> auto mapping."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_priority": 99}, priority=PRIORITY_MEDIUM)
    await uut.deliver(e)

    assert e.calls[0].action_data["data"]["priority"] == 0  # type: ignore[index] # PRIORITY_MEDIUM -> 0


async def test_priority_override_non_numeric_uses_mapping() -> None:
    """pushover_priority non-numeric -> auto mapping with warning."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_priority": "very-high"}, priority=PRIORITY_HIGH)
    await uut.deliver(e)

    assert e.calls[0].action_data["data"]["priority"] == 1  # type: ignore[index] # PRIORITY_HIGH -> 1


# ---------------------------------------------------------------------------
# Emergency mode (priority=2)
# ---------------------------------------------------------------------------


async def test_emergency_auto_retry_expire() -> None:
    """Emergency without retry/expire -> uses defaults (60s / 3600s)."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(ctx, priority=PRIORITY_CRITICAL)
        await uut.deliver(e)

    push_data = e.calls[0].action_data["data"]  # type: ignore[index]
    assert push_data["priority"] == 2
    assert push_data["retry"] == 60
    assert push_data["expire"] == 3600


async def test_emergency_explicit_retry_expire() -> None:
    """Emergency with explicit retry/expire -> used as specified."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(
            ctx,
            data={"pushover_retry": 120, "pushover_expire": 7200},
            priority=PRIORITY_CRITICAL,
        )
        await uut.deliver(e)

    push_data = e.calls[0].action_data["data"]  # type: ignore[index]
    assert push_data["retry"] == 120
    assert push_data["expire"] == 7200


async def test_emergency_retry_clamped_to_minimum() -> None:
    """Retry < 30 is clamped to 30 (Pushover API limit)."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(
            ctx,
            data={"pushover_retry": 10},
            priority=PRIORITY_CRITICAL,
        )
        await uut.deliver(e)

    assert e.calls[0].action_data["data"]["retry"] == 30  # type: ignore[index]


async def test_emergency_expire_clamped_to_maximum() -> None:
    """Expire > 10800 is clamped to 10800 (Pushover API limit = 3 hours)."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(
            ctx,
            data={"pushover_expire": 99999},
            priority=PRIORITY_CRITICAL,
        )
        await uut.deliver(e)

    assert e.calls[0].action_data["data"]["expire"] == 10800  # type: ignore[index]


async def test_emergency_callback_included() -> None:
    """pushover_callback in emergency -> included in the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(
            ctx,
            data={"pushover_callback": "https://homeassistant.local/api/webhook/ack"},
            priority=PRIORITY_CRITICAL,
        )
        await uut.deliver(e)

    assert e.calls[0].action_data["data"]["callback"] == "https://homeassistant.local/api/webhook/ack"  # type: ignore[index]


async def test_non_emergency_no_retry_expire() -> None:
    """Non-emergency priority -> retry and expire are NOT in the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, priority=PRIORITY_HIGH)
    await uut.deliver(e)

    push_data = e.calls[0].action_data["data"]  # type: ignore[index]
    assert "retry" not in push_data
    assert "expire" not in push_data
    assert "callback" not in push_data


# ---------------------------------------------------------------------------
# Optional fields
# ---------------------------------------------------------------------------


async def test_deliver_all_optional_fields() -> None:
    """sound, url, url_title, html, ttl, device all included in the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(
        ctx,
        data={
            "pushover_sound": "siren",
            "pushover_url": "https://homeassistant.local:8123",
            "pushover_url_title": "Open HA",
            "pushover_html": True,
            "pushover_ttl": 3600,
            "pushover_device": "iphone",
        },
    )
    await uut.deliver(e)

    push_data = e.calls[0].action_data["data"]  # type: ignore[index]
    assert push_data["sound"] == "siren"
    assert push_data["url"] == "https://homeassistant.local:8123"
    assert push_data["url_title"] == "Open HA"
    assert push_data["html"] == 1
    assert push_data["ttl"] == 3600
    assert push_data["device"] == "iphone"


async def test_html_flag_maps_to_integer_1() -> None:
    """pushover_html=True -> html=1 (integer, as required by Pushover API)."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_html": True})
    await uut.deliver(e)

    assert e.calls[0].action_data["data"]["html"] == 1  # type: ignore[index]


async def test_html_false_not_in_payload() -> None:
    """pushover_html=False -> 'html' absent from the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_html": False})
    await uut.deliver(e)

    assert "html" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_html_string_yaml_true() -> None:
    """pushover_html='true' (YAML string) -> html=1 thanks to boolify()."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_html": "true"})
    await uut.deliver(e)

    assert e.calls[0].action_data["data"]["html"] == 1  # type: ignore[index]


async def test_html_string_yaml_false() -> None:
    """pushover_html='false' (YAML string) -> 'html' absent thanks to boolify()."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_html": "false"})
    await uut.deliver(e)

    assert "html" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_ttl_invalid_type_ignored() -> None:
    """pushover_ttl non-numeric -> ignored with warning, ttl absent from payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx, data={"pushover_ttl": "not-a-number"})
    await uut.deliver(e)

    assert "ttl" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_optional_fields_absent_when_not_set() -> None:
    """Optional fields absent when not specified in data."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(ctx)
    await uut.deliver(e)

    push_data = e.calls[0].action_data["data"]  # type: ignore[index]
    for key in ("sound", "url", "url_title", "html", "ttl", "device", "attachment", "callback"):
        assert key not in push_data, f"Field '{key}' should not be in the payload"


# ---------------------------------------------------------------------------
# pushover_* keys must not leak into the payload
# ---------------------------------------------------------------------------


async def test_pushover_keys_not_leaked_to_service_payload() -> None:
    """No pushover_*-prefixed key should appear in the service payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    e = _envelope(
        ctx,
        data={
            "pushover_sound": "siren",
            "pushover_priority": 1,
            "pushover_url": "https://example.com",
            "pushover_url_title": "Link",
            "pushover_html": True,
            "pushover_ttl": 3600,
            "pushover_device": "iphone",
            "pushover_attach_image": False,
        },
    )
    await uut.deliver(e)

    ad = e.calls[0].action_data
    # Check both the top level and the nested data
    leaked_top = [k for k in ad if k.startswith("pushover_")]  # type: ignore[union-attr]
    leaked_data = [k for k in ad.get("data", {}) if k.startswith("pushover_")]  # type: ignore[union-attr]
    assert leaked_top == [], f"pushover_* keys at top level: {leaked_top}"
    assert leaked_data == [], f"pushover_* keys in nested data: {leaked_data}"


# ---------------------------------------------------------------------------
# pushover_attach_image
# ---------------------------------------------------------------------------


async def test_attach_image_calls_grab_image() -> None:
    """pushover_attach_image=True -> grab_image() is called."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    mock_path = MagicMock()
    mock_path.__str__.return_value = "/config/www/supernotify_pushover_snap.jpg"  # type: ignore[attr-defined]

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=mock_path),
    ) as mock_grab:
        e = _envelope(ctx, data={"pushover_attach_image": True})
        await uut.deliver(e)

        mock_grab.assert_called_once()

    assert e.calls[0].action_data["data"]["attachment"] == "/config/www/supernotify_pushover_snap.jpg"  # type: ignore[index]


async def test_attach_image_grab_returns_none_no_attachment() -> None:
    """grab_image() returns None -> 'attachment' absent from the payload."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ):
        e = _envelope(ctx, data={"pushover_attach_image": True})
        await uut.deliver(e)

    assert "attachment" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_attach_image_false_no_grab_call() -> None:
    """pushover_attach_image=False -> grab_image() is NOT called."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ) as mock_grab:
        e = _envelope(ctx, data={"pushover_attach_image": False})
        await uut.deliver(e)

        mock_grab.assert_not_called()

    assert "attachment" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_attach_image_grab_exception_delivery_continues() -> None:
    """If grab_image() raises, the notification is delivered without attachment."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(side_effect=Exception("camera unreachable")),
    ):
        e = _envelope(ctx, data={"pushover_attach_image": True})
        result = await uut.deliver(e)

    assert result is True
    assert "attachment" not in e.calls[0].action_data["data"]  # type: ignore[index]


async def test_attach_image_string_yaml_true() -> None:
    """pushover_attach_image='true' (YAML string) -> grab_image() called via boolify()."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        new=AsyncMock(return_value=None),
    ) as mock_grab:
        e = _envelope(ctx, data={"pushover_attach_image": "true"})
        await uut.deliver(e)

        mock_grab.assert_called_once()


# ---------------------------------------------------------------------------
# validate_action
# ---------------------------------------------------------------------------


def test_validate_action_valid_notify_service() -> None:
    """notify.pushover_home -> True."""
    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.validate_action("notify.pushover_home") is True


def test_validate_action_valid_any_notify() -> None:
    """notify.any_name -> True."""
    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.validate_action("notify.another_pushover") is True


def test_validate_action_none_returns_false() -> None:
    """None -> False."""
    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.validate_action(None) is False


def test_validate_action_wrong_domain_returns_false() -> None:
    """pushover.send -> False (not a notify.*)."""
    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.validate_action("pushover.send") is False


def test_validate_action_empty_string_returns_false() -> None:
    """Empty string -> False."""
    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.validate_action("") is False


# ---------------------------------------------------------------------------
# Service call failure -> return False
# ---------------------------------------------------------------------------


async def test_service_call_exception_returns_false() -> None:
    """If the service call raises, deliver() returns False."""
    ctx = _ctx()
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    ctx.hass.services.async_call.side_effect = Exception("Pushover unreachable")  # type: ignore

    result = await uut.deliver(_envelope(ctx))

    assert result is False


# ---------------------------------------------------------------------------
# supported_features
# ---------------------------------------------------------------------------


def test_supported_features_include_snapshot_image() -> None:
    """SNAPSHOT_IMAGE must be declared (required v1.14.0+ for image-attaching transports)."""
    from custom_components.supernotify.model import TransportFeature

    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.supported_features & TransportFeature.SNAPSHOT_IMAGE


def test_supported_features_include_message_title_images() -> None:
    """MESSAGE, TITLE and IMAGES must be declared."""
    from custom_components.supernotify.model import TransportFeature

    transport = PushoverTransport(MagicMock(), MagicMock())
    assert transport.supported_features & TransportFeature.MESSAGE
    assert transport.supported_features & TransportFeature.TITLE
    assert transport.supported_features & TransportFeature.IMAGES
