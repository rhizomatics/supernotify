"""Tests for the Kodi transport.

Target file: custom_components/supernotify/transports/kodi.py

Coverage:
- TransportFeature flags, default_config, validate_action, transport name
- Target entity filtering (media_player.* prefix, dedupe, non-string skip)
- deliver(): happy path, title fallback "Notification", priority -> icon
  mapping (all 5 priorities + unknown/None), kodi_icon override,
  kodi_displaytime coercion (str / float / invalid / below minimum clamp),
  kodi_attach_image (snapshot_url from envelope.media wins, fallback
  grab_image + media_storage.object_url, grab failure, no URL resolvable,
  image URL wins over kodi_icon), URL absolutisation against internal_url,
  no valid target -> False + record_error + no service call, exact payload
  shape with no residual data key passthrough (JSON-RPC quirk), entity
  target_data, call_action failure, boolify on YAML string bools,
  force_resend/spoken_message not popped and envelope.data not mutated

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_kodi.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.supernotify.model import TargetRequired, TransportFeature
from custom_components.supernotify.transports.kodi import (
    DEFAULT_DISPLAYTIME,
    DEFAULT_TITLE,
    MIN_DISPLAYTIME,
    KodiTransport,
    _coerce_int,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

KODI_ENTITY = "media_player.kodi_living_room"
KODI_ENTITY_2 = "media_player.kodi_bedroom"
INTERNAL_URL = "http://192.168.0.123:8123"
OBJECT_URL = "http://192.168.0.123:8123/supernotify/media/snapshot.jpg"


def _make_transport(
    call_action_result: bool = True,
    object_url: str | None = OBJECT_URL,
    object_url_raises: bool = False,
    internal_url: str = INTERNAL_URL,
) -> Any:
    """Construct a KodiTransport with hass_api / context / call_action mocked.

    Returns Any (not KodiTransport): call_action/record_error below are replaced with
    Mocks, which mypy rejects as assignments to real bound methods on the concrete type.
    """
    transport: Any = KodiTransport.__new__(KodiTransport)
    transport.hass_api = MagicMock()
    transport.hass_api.call_service = AsyncMock(return_value=None)
    transport.hass_api.internal_url = internal_url
    transport.hass_api.external_url = "https://example.duckdns.org"
    transport.context = MagicMock()
    if object_url_raises:
        transport.context.media_storage.object_url = AsyncMock(side_effect=OSError("no media path"))
    else:
        transport.context.media_storage.object_url = AsyncMock(return_value=object_url)
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
    grab_image_value: Any = None,
    grab_image_raises: bool = False,
) -> MagicMock:
    """Build a mock Envelope exposing the attributes deliver() consumes."""
    envelope = MagicMock()
    envelope.message = message
    envelope.title = title
    envelope.data = data if data is not None else {}
    envelope.priority = priority
    envelope.media = media if media is not None else {}
    envelope.target = MagicMock()
    envelope.target.entity_ids = [KODI_ENTITY] if targets is None else targets
    if grab_image_raises:
        envelope.grab_image = AsyncMock(side_effect=OSError("camera offline"))
    else:
        envelope.grab_image = AsyncMock(return_value=grab_image_value)
    return envelope


def _action_data(transport: Any) -> dict[str, Any]:
    """Return the action_data kwarg of the most recent call_action invocation."""
    return transport.call_action.call_args.kwargs["action_data"]


def _target_data(transport: Any) -> dict[str, Any]:
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
    # Kodi overlay has no action buttons and no spoken output
    assert not features & TransportFeature.ACTIONS
    assert not features & TransportFeature.SPOKEN


def test_default_config() -> None:
    uut = _make_transport()
    config = uut.default_config
    assert config.delivery_defaults.action == "kodi.call_method"
    assert config.delivery_defaults.target_required == TargetRequired.ALWAYS


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("kodi.call_method", True),
        ("kodi.add_to_playlist", False),
        ("notify.kodi", False),
        ("media_player.play_media", False),
        (None, False),
        ("", False),
    ],
)
def test_validate_action(action: str | None, expected: bool) -> None:
    uut = _make_transport()
    assert uut.validate_action(action) is expected


def test_transport_name() -> None:
    assert KodiTransport.name == "kodi"


# ---------------------------------------------------------------------------
# _coerce_int
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5000, 5000),
        ("5000", 5000),
        (6000.7, 6000),
        ("6000.7", 6000),
        ("abc", None),
        (None, None),
        ({}, None),
        ([1500], None),
    ],
)
def test_coerce_int(value: Any, expected: int | None) -> None:
    assert _coerce_int(value) == expected


# ---------------------------------------------------------------------------
# Target entity filtering
# ---------------------------------------------------------------------------


def test_select_targets_filters_and_dedupes() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        targets=[KODI_ENTITY, "light.kitchen", KODI_ENTITY_2, KODI_ENTITY, "!room:server"],
    )
    assert uut.select_targets(envelope) == [KODI_ENTITY, KODI_ENTITY_2]


def test_select_targets_non_string_target_skipped() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[12345, None, KODI_ENTITY])
    assert uut.select_targets(envelope) == [KODI_ENTITY]


def test_select_targets_no_target_object() -> None:
    uut = _make_transport()
    envelope = _make_envelope()
    envelope.target = None
    assert uut.select_targets(envelope) == []


# ---------------------------------------------------------------------------
# Happy path delivery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_basic_message() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="Hello from SuperNotify", title="Alert")

    result = await uut.deliver(envelope)

    assert result is True
    uut.call_action.assert_awaited_once()
    action_data = _action_data(uut)
    assert action_data["method"] == "GUI.ShowNotification"
    assert action_data["title"] == "Alert"
    assert action_data["message"] == "Hello from SuperNotify"
    assert action_data["image"] == "info"
    assert action_data["displaytime"] == DEFAULT_DISPLAYTIME
    assert _target_data(uut) == {"entity_id": [KODI_ENTITY]}


@pytest.mark.asyncio
async def test_deliver_multi_target() -> None:
    uut = _make_transport()
    envelope = _make_envelope(targets=[KODI_ENTITY, KODI_ENTITY_2])

    result = await uut.deliver(envelope)

    assert result is True
    assert _target_data(uut) == {"entity_id": [KODI_ENTITY, KODI_ENTITY_2]}


@pytest.mark.asyncio
async def test_deliver_none_message_sends_empty_string() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message=None, title="Alert")

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["message"] == ""


# ---------------------------------------------------------------------------
# Title fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_title_fallback_when_missing() -> None:
    # GUI.ShowNotification requires a non-empty title
    uut = _make_transport()
    envelope = _make_envelope(title=None)

    await uut.deliver(envelope)

    assert _action_data(uut)["title"] == DEFAULT_TITLE


@pytest.mark.asyncio
async def test_deliver_title_fallback_when_empty() -> None:
    uut = _make_transport()
    envelope = _make_envelope(title="")

    await uut.deliver(envelope)

    assert _action_data(uut)["title"] == DEFAULT_TITLE


# ---------------------------------------------------------------------------
# Priority -> icon mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("priority", "expected_icon"),
    [
        ("critical", "error"),
        ("high", "warning"),
        ("medium", "info"),
        ("low", "info"),
        ("minimum", "info"),
    ],
)
async def test_deliver_priority_icon_mapping(priority: str, expected_icon: str) -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority=priority)

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == expected_icon


@pytest.mark.asyncio
async def test_deliver_none_priority_defaults_to_info() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority=None)

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == "info"


@pytest.mark.asyncio
async def test_deliver_unknown_priority_defaults_to_info() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority="bogus")

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == "info"


# ---------------------------------------------------------------------------
# kodi_icon override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_icon_override_native() -> None:
    uut = _make_transport()
    envelope = _make_envelope(priority="critical", data={"kodi_icon": "warning"})

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == "warning"


@pytest.mark.asyncio
async def test_deliver_icon_override_custom_url() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"kodi_icon": "http://example.com/icon.png"})

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == "http://example.com/icon.png"


# ---------------------------------------------------------------------------
# kodi_displaytime coercion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (5000, 5000),
        ("5000", 5000),
        (6000.7, 6000),
        ("abc", DEFAULT_DISPLAYTIME),  # invalid -> default
        ({}, DEFAULT_DISPLAYTIME),  # invalid type -> default
        (500, MIN_DISPLAYTIME),  # below Kodi minimum -> clamped
        ("100", MIN_DISPLAYTIME),  # string below minimum -> clamped
        (MIN_DISPLAYTIME, MIN_DISPLAYTIME),  # exactly the minimum
    ],
)
async def test_deliver_displaytime_coercion(raw: Any, expected: int) -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"kodi_displaytime": raw})

    await uut.deliver(envelope)

    assert _action_data(uut)["displaytime"] == expected


@pytest.mark.asyncio
async def test_deliver_displaytime_default_when_unset() -> None:
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    assert _action_data(uut)["displaytime"] == DEFAULT_DISPLAYTIME


# ---------------------------------------------------------------------------
# Image attachment (URL resolution)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_attach_image_from_media_snapshot_url() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"kodi_attach_image": True},
        media={"snapshot_url": "http://192.168.0.50/snapshot.jpg"},
    )

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["image"] == "http://192.168.0.50/snapshot.jpg"
    # snapshot_url wins: no need to grab a fresh image
    envelope.grab_image.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_attach_image_relative_snapshot_url_absolutised() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"kodi_attach_image": True},
        media={"snapshot_url": "/api/camera_proxy/camera.front_door"},
    )

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == f"{INTERNAL_URL}/api/camera_proxy/camera.front_door"


@pytest.mark.asyncio
async def test_deliver_attach_image_fallback_grab_and_object_url() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"kodi_attach_image": True},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    envelope.grab_image.assert_awaited_once()
    uut.context.media_storage.object_url.assert_awaited_once_with(Path("/media/supernotify/snapshot.jpg"))
    assert _action_data(uut)["image"] == OBJECT_URL


@pytest.mark.asyncio
async def test_deliver_attach_image_no_image_available_keeps_priority_icon() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        priority="high",
        data={"kodi_attach_image": True},
        grab_image_value=None,
    )

    result = await uut.deliver(envelope)

    # Text overlay still delivered with the priority icon
    assert result is True
    assert _action_data(uut)["image"] == "warning"


@pytest.mark.asyncio
async def test_deliver_attach_image_grab_raises() -> None:
    uut = _make_transport()
    envelope = _make_envelope(data={"kodi_attach_image": True}, grab_image_raises=True)

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["image"] == "info"


@pytest.mark.asyncio
async def test_deliver_attach_image_object_url_none_keeps_icon() -> None:
    uut = _make_transport(object_url=None)
    envelope = _make_envelope(
        data={"kodi_attach_image": True},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["image"] == "info"


@pytest.mark.asyncio
async def test_deliver_attach_image_object_url_raises_keeps_icon() -> None:
    uut = _make_transport(object_url_raises=True)
    envelope = _make_envelope(
        data={"kodi_attach_image": True},
        grab_image_value=Path("/media/supernotify/snapshot.jpg"),
    )

    result = await uut.deliver(envelope)

    assert result is True
    assert _action_data(uut)["image"] == "info"


@pytest.mark.asyncio
async def test_deliver_attach_image_wins_over_kodi_icon() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={"kodi_attach_image": True, "kodi_icon": "error"},
        media={"snapshot_url": "http://192.168.0.50/snapshot.jpg"},
    )

    await uut.deliver(envelope)

    assert _action_data(uut)["image"] == "http://192.168.0.50/snapshot.jpg"


@pytest.mark.asyncio
async def test_deliver_no_attach_image_by_default() -> None:
    uut = _make_transport()
    envelope = _make_envelope(media={"snapshot_url": "http://192.168.0.50/snapshot.jpg"})

    await uut.deliver(envelope)

    envelope.grab_image.assert_not_awaited()
    assert _action_data(uut)["image"] == "info"


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
        data={"kodi_attach_image": yaml_value},
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
    envelope = _make_envelope(targets=["light.kitchen", "notify.mobile_app_phone"])

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
    envelope = _make_envelope(targets=["light.kitchen", KODI_ENTITY, "sensor.x", KODI_ENTITY_2])

    result = await uut.deliver(envelope)

    assert result is True
    assert _target_data(uut) == {"entity_id": [KODI_ENTITY, KODI_ENTITY_2]}


# ---------------------------------------------------------------------------
# JSON-RPC quirk: no residual passthrough, exact payload shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_no_residual_data_passthrough() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "kodi_displaytime": 5000,
            "generic_key": "generic_value",
            "another_key": 123,
        },
    )

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    # Unknown keys would become bogus JSON-RPC parameters and fail the call
    assert "generic_key" not in action_data
    assert "another_key" not in action_data


@pytest.mark.asyncio
async def test_deliver_exact_payload_shape() -> None:
    uut = _make_transport()
    envelope = _make_envelope(message="body", title="Head", priority="high")

    await uut.deliver(envelope)

    action_data = _action_data(uut)
    assert set(action_data) == {"method", "title", "message", "image", "displaytime"}
    assert action_data == {
        "method": "GUI.ShowNotification",
        "title": "Head",
        "message": "body",
        "image": "warning",
        "displaytime": DEFAULT_DISPLAYTIME,
    }


@pytest.mark.asyncio
async def test_deliver_kodi_keys_not_in_payload() -> None:
    uut = _make_transport()
    envelope = _make_envelope(
        data={
            "kodi_displaytime": 3000,
            "kodi_icon": "error",
            "kodi_attach_image": False,
        },
    )

    await uut.deliver(envelope)

    assert not any(k.startswith("kodi_") for k in _action_data(uut))


@pytest.mark.asyncio
async def test_deliver_internal_keys_not_forwarded_and_data_untouched() -> None:
    # force_resend / spoken_message are filtered upstream by notification.py;
    # if they ever reach the envelope they must not leak into the JSON-RPC
    # payload, and the transport must not mutate envelope.data
    uut = _make_transport()
    data = {"force_resend": True, "spoken_message": "speak", "kodi_displaytime": 4000}
    envelope = _make_envelope(data=data)

    result = await uut.deliver(envelope)

    assert result is True
    action_data = _action_data(uut)
    assert "force_resend" not in action_data
    assert "spoken_message" not in action_data
    # envelope.data is copied, never mutated by the pops
    assert envelope.data == {"force_resend": True, "spoken_message": "speak", "kodi_displaytime": 4000}


# ---------------------------------------------------------------------------
# Service call failure and call_action wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_call_action_failure_returns_false() -> None:
    uut = _make_transport(call_action_result=False)
    envelope = _make_envelope()

    result = await uut.deliver(envelope)

    assert result is False
    uut.call_action.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_uses_call_action_with_entity_target_data() -> None:
    # call_action derives kodi.call_method from delivery.action defaults;
    # deliver() must not override it with a qualified_action, and the
    # entities go in target_data (entity service), not in action_data
    uut = _make_transport()
    envelope = _make_envelope()

    await uut.deliver(envelope)

    kwargs = uut.call_action.call_args.kwargs
    assert "action_data" in kwargs
    assert "target_data" in kwargs
    assert "qualified_action" not in kwargs
    assert "entity_id" not in kwargs["action_data"]
