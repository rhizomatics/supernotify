"""Unit tests for LaMetric transport (SuperNotify).

Covers:
  - Happy path: lametric.message (text notification)
  - Happy path: lametric.chart (bar chart)
  - Priority mapping: all 5 SuperNotify levels → LaMetric priority/cycles/icon_type/sound/icon
  - Data key overrides: lametric_sound, lametric_icon, lametric_cycles, lametric_icon_type
  - lametric_chart_data: valid list, invalid type
  - lametric_simplify: True/False, YAML string "true"/"false" via boolify()
  - device_id: present in envelope.data, missing → return False
  - lametric_* keys: popped and NOT passed to HA service
  - call_action return values: True / False propagated
  - cycles=0 (permanent) treated as valid (not falsy)

Pattern: call_action() is mocked on the transport instance. Our transport uses
self.call_action(envelope, qualified_action="lametric.message"/".chart", action_data=...)
Internals of call_action (hass_api, try/except) are NOT tested here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.supernotify.const import TRANSPORT_LAMETRIC
from custom_components.supernotify.model import (
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transports.lametric import LaMetricTransport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(
    message: str = "Test message",
    title: str | None = None,
    priority: str = "medium",
    data: dict | None = None,
):
    """Build a minimal mock Envelope.

    device_id lives in envelope.data (flat dict), as per SuperNotify Rule #8.
    Default: data={"device_id": "deadbeef01234567deadbeef01234567"}.
    Pass data={} to test missing device_id.
    """
    env = MagicMock()
    env.message = message
    env.title = title
    env.priority = priority
    if data is None:
        env.data = {"device_id": "deadbeef01234567deadbeef01234567"}
    else:
        env.data = data
    return env


def _make_transport() -> LaMetricTransport:
    """Instantiate LaMetricTransport with mocked context."""
    ctx = MagicMock()
    ctx.hass_api = MagicMock()
    return LaMetricTransport(ctx)


# ---------------------------------------------------------------------------
# Basic identity / metadata
# ---------------------------------------------------------------------------


def test_transport_name():
    t = _make_transport()
    assert t.name == TRANSPORT_LAMETRIC
    assert t.name == "lametric"


def test_supported_features_message_and_title():
    t = _make_transport()
    f = t.supported_features
    assert f & TransportFeature.MESSAGE
    assert f & TransportFeature.TITLE


def test_supported_features_no_images_actions_spoken():
    t = _make_transport()
    f = t.supported_features
    assert not (f & TransportFeature.IMAGES)
    assert not (f & TransportFeature.ACTIONS)
    assert not (f & TransportFeature.SPOKEN)


def test_default_config_target_required_never():
    t = _make_transport()
    cfg = t.default_config
    assert isinstance(cfg, TransportConfig)
    assert cfg.delivery_defaults.target_required == TargetRequired.NEVER


def test_validate_action_always_true():
    t = _make_transport()
    assert t.validate_action(None) is True
    assert t.validate_action("anything") is True
    assert t.validate_action("lametric.message") is True


# ---------------------------------------------------------------------------
# Happy path — lametric.message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_message_happy_path():
    t = _make_transport()
    env = _make_envelope(message="Hello LaMetric", priority="medium")
    t.call_action = AsyncMock(return_value=True)

    result = await t.deliver(env)

    assert result is True
    t.call_action.assert_awaited_once()
    _, kw = t.call_action.call_args
    assert kw["qualified_action"] == "lametric.message"
    ad = kw["action_data"]
    assert ad["device_id"] == "deadbeef01234567deadbeef01234567"
    assert ad["message"] == "Hello LaMetric"
    assert ad["priority"] == "info"  # medium → info
    assert ad["cycles"] == 1  # medium → 1
    assert ad["icon_type"] == "info"  # medium → info
    assert ad["icon"] == "i2867"  # medium → i2867
    assert ad["sound"] == "notification"  # medium → notification


@pytest.mark.asyncio
async def test_deliver_message_returns_false_when_call_action_fails():
    t = _make_transport()
    env = _make_envelope()
    t.call_action = AsyncMock(return_value=False)

    assert await t.deliver(env) is False


# ---------------------------------------------------------------------------
# device_id — missing cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deliver_missing_device_id_returns_false():
    t = _make_transport()
    env = _make_envelope(data={})  # no device_id
    t.call_action = AsyncMock(return_value=True)

    result = await t.deliver(env)

    assert result is False
    t.call_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_deliver_none_data_returns_false():
    t = _make_transport()
    env = _make_envelope()
    env.data = None  # envelope.data is None
    t.call_action = AsyncMock(return_value=True)

    result = await t.deliver(env)

    assert result is False
    t.call_action.assert_not_awaited()


# ---------------------------------------------------------------------------
# Priority mapping — all 5 levels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sn_priority", "exp_priority", "exp_cycles", "exp_icon_type", "exp_sound", "exp_icon"),
    [
        ("critical", "critical", 0, "alert", "alarm1", "a1784"),
        ("high", "warning", 2, "alert", "knock-knock", "i140"),
        ("medium", "info", 1, "info", "notification", "i2867"),
        ("low", "info", 1, "none", None, "i2867"),
        ("minimum", "info", 1, "none", None, None),
    ],
)
async def test_priority_mapping(sn_priority, exp_priority, exp_cycles, exp_icon_type, exp_sound, exp_icon):
    t = _make_transport()
    env = _make_envelope(priority=sn_priority)
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    ad = kw["action_data"]

    assert ad["priority"] == exp_priority, f"priority wrong for {sn_priority}"
    assert ad["cycles"] == exp_cycles, f"cycles wrong for {sn_priority}"
    assert ad["icon_type"] == exp_icon_type, f"icon_type wrong for {sn_priority}"

    if exp_sound is None:
        assert "sound" not in ad, f"sound must be absent for {sn_priority}"
    else:
        assert ad["sound"] == exp_sound, f"sound wrong for {sn_priority}"

    if exp_icon is None:
        assert "icon" not in ad, f"icon must be absent for {sn_priority}"
    else:
        assert ad["icon"] == exp_icon, f"icon wrong for {sn_priority}"


@pytest.mark.asyncio
async def test_priority_none_falls_back_to_medium():
    """envelope.priority=None must fall back to 'medium' defaults."""
    t = _make_transport()
    env = _make_envelope(priority=None)
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    ad = kw["action_data"]
    assert ad["priority"] == "info"
    assert ad["cycles"] == 1
    assert ad["icon_type"] == "info"
    assert ad["sound"] == "notification"
    assert ad["icon"] == "i2867"


# ---------------------------------------------------------------------------
# Data key overrides
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lametric_sound_override():
    t = _make_transport()
    env = _make_envelope(priority="low", data={"device_id": "abc", "lametric_sound": "alarm5"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["sound"] == "alarm5"


@pytest.mark.asyncio
async def test_lametric_icon_override():
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc", "lametric_icon": "i9999"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["icon"] == "i9999"


@pytest.mark.asyncio
async def test_lametric_cycles_override():
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc", "lametric_cycles": 5})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["cycles"] == 5


@pytest.mark.asyncio
async def test_lametric_cycles_zero_override():
    """cycles=0 means permanent — must NOT be treated as falsy and discarded."""
    t = _make_transport()
    env = _make_envelope(priority="medium", data={"device_id": "abc", "lametric_cycles": 0})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["cycles"] == 0  # 0 is valid, not falsy-discarded


@pytest.mark.asyncio
async def test_lametric_icon_type_override():
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc", "lametric_icon_type": "alert"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["icon_type"] == "alert"


# ---------------------------------------------------------------------------
# lametric_* keys NOT leaked to HA service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lametric_keys_not_in_action_data():
    """All lametric_* keys must be popped before the payload is sent."""
    t = _make_transport()
    env = _make_envelope(
        data={
            "device_id": "abc",
            "lametric_sound": "alarm3",
            "lametric_icon": "i100",
            "lametric_cycles": 2,
            "lametric_icon_type": "info",
            "lametric_simplify": True,
        }
    )
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    ad = kw["action_data"]
    for key in (
        "lametric_sound",
        "lametric_icon",
        "lametric_cycles",
        "lametric_icon_type",
        "lametric_simplify",
        "lametric_chart_data",
    ):
        assert key not in ad, f"'{key}' must NOT appear in action_data sent to HA service"


# ---------------------------------------------------------------------------
# lametric_simplify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simplify_false_preserves_message():
    t = _make_transport()
    original = "Check http://example.com for details!"
    env = _make_envelope(message=original, data={"device_id": "abc"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["message"] == original


@pytest.mark.asyncio
async def test_simplify_true_calls_simplify_method():
    t = _make_transport()
    t.simplify = MagicMock(return_value="Simplified")
    env = _make_envelope(message="Long msg http://url.com", data={"device_id": "abc", "lametric_simplify": True})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    t.simplify.assert_called_once_with("Long msg http://url.com", strip_urls=True)
    _, kw = t.call_action.call_args
    assert kw["action_data"]["message"] == "Simplified"


@pytest.mark.asyncio
async def test_simplify_yaml_string_true():
    """lametric_simplify='true' (YAML string) — boolify() must treat as True."""
    t = _make_transport()
    t.simplify = MagicMock(return_value="Short")
    env = _make_envelope(message="Verbose", data={"device_id": "abc", "lametric_simplify": "true"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    t.simplify.assert_called_once()


@pytest.mark.asyncio
async def test_simplify_yaml_string_false():
    """lametric_simplify='false' (YAML string) — boolify() must NOT simplify.

    This is the classic Python trap: bool('false') == True.
    boolify() must handle it correctly.
    """
    t = _make_transport()
    t.simplify = MagicMock(return_value="Short")
    env = _make_envelope(message="Original", data={"device_id": "abc", "lametric_simplify": "false"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    t.simplify.assert_not_called()
    _, kw = t.call_action.call_args
    assert kw["action_data"]["message"] == "Original"


# ---------------------------------------------------------------------------
# Chart path — lametric.chart
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chart_happy_path():
    t = _make_transport()
    chart = [10, 30, 50, 80, 60, 20]
    env = _make_envelope(priority="high", data={"device_id": "abc123", "lametric_chart_data": chart})
    t.call_action = AsyncMock(return_value=True)

    result = await t.deliver(env)

    assert result is True
    _, kw = t.call_action.call_args
    assert kw["qualified_action"] == "lametric.chart"
    ad = kw["action_data"]
    assert ad["device_id"] == "abc123"
    assert ad["data"] == chart  # field name is "data", NOT "chart_data"
    assert ad["priority"] == "warning"  # high → warning
    assert ad["cycles"] == 2  # high → 2
    assert ad["icon_type"] == "alert"  # high → alert
    assert ad["sound"] == "knock-knock"
    assert "message" not in ad  # no message in chart payload
    assert "icon" not in ad  # no icon in chart payload


@pytest.mark.asyncio
async def test_chart_critical_priority():
    t = _make_transport()
    env = _make_envelope(priority="critical", data={"device_id": "abc", "lametric_chart_data": [1, 2, 3]})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    ad = kw["action_data"]
    assert ad["priority"] == "critical"
    assert ad["cycles"] == 0
    assert ad["sound"] == "alarm1"


@pytest.mark.asyncio
async def test_chart_low_priority_no_sound():
    t = _make_transport()
    env = _make_envelope(priority="low", data={"device_id": "abc", "lametric_chart_data": [5, 10]})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert "sound" not in kw["action_data"]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_value", ["not-a-list", 42, {"a": 1}])
async def test_chart_invalid_type_returns_false(bad_value):
    """lametric_chart_data must be a list — any other type → False, no service call."""
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc", "lametric_chart_data": bad_value})
    t.call_action = AsyncMock(return_value=True)

    result = await t.deliver(env)

    assert result is False, f"Expected False for chart_data={bad_value!r}"
    t.call_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_chart_sound_override():
    t = _make_transport()
    env = _make_envelope(
        priority="medium", data={"device_id": "abc", "lametric_chart_data": [1, 2, 3], "lametric_sound": "win"}
    )
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["action_data"]["sound"] == "win"


# ---------------------------------------------------------------------------
# qualified_action routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_path_service_name():
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc"})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["qualified_action"] == "lametric.message"


@pytest.mark.asyncio
async def test_chart_path_service_name():
    t = _make_transport()
    env = _make_envelope(data={"device_id": "abc", "lametric_chart_data": [1, 2]})
    t.call_action = AsyncMock(return_value=True)

    await t.deliver(env)

    _, kw = t.call_action.call_args
    assert kw["qualified_action"] == "lametric.chart"
