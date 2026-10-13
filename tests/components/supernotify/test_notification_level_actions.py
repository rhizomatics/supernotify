from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import (
    MOBILE_ACTION_SCHEMA,
    NOTIFY_ACTION_SCHEMA,
    SUPERNOTIFY_YAML_SCHEMA,
    EnvelopeOutcome,
)
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from custom_components.supernotify.transports.ntfy import NtfyTransport
from custom_components.supernotify.transports.telegram import _build_inline_keyboard
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def fixture(hass: HomeAssistant) -> TestingContext:
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
recipients:
  - person: person.joe_mcphee
    mobile_devices:
        - mobile_app_id: mobile_app_joe_nokia

delivery:
  mobile_push:
    transport: mobile_push
  ntfy:
    transport: ntfy
    data:
      ntfy_device_id: dev1
cameras:
  - camera: camera.porch
    alias: Porch
scenarios:
  porch:
    media:
      camera_entity_id: camera.porch
    action_groups:
      - silence_actions
  cameras:
    action_groups:
      - camera_actions
  alarm:
    action_groups:
      - alarm_actions

action_groups:
  silence_actions:
    - action_template: "SILENCE_{{ camera.entity_id }}"
      title_template: "Silence {{ camera.alias }}"
  camera_actions:
    - action: CAMERA_SILENCE
      title: Silence
    - level: notification
      uri_template: "homeassistant://navigate/lovelace/{{ notification_priority }}"
  alarm_actions:
    - action_template: "ALARM_{{ notification_priority | upper }}"
      title_template: "Alarm at {{ notification_priority }}"
      level: action
    - level: notification
      uri: https://my.home/alarm
      """,
        services={"notify": ["mobile_app_joe_nokia"], "ntfy": ["publish"]},
        viable_transport_types=[MobilePushTransport, NtfyTransport],
    )
    await ctx.test_initialize()
    return ctx


async def _push_data(ctx: TestingContext, action_data: dict[str, Any]) -> dict[str, Any]:
    uut = Notification(ctx, "testing 123", action_data=action_data)
    await uut.initialize()
    await uut.deliver()
    envelope = uut.deliveries["mobile_push"][EnvelopeOutcome.SUCCESS][0]  # type:ignore[index]
    return envelope.calls[0].action_data["data"]  # type:ignore[index,union-attr]


async def test_ad_hoc_notification_level_action(fixture: TestingContext) -> None:
    data = await _push_data(
        fixture,
        {
            "actions": [
                {"action": "OPEN_GATE", "title": "Open the gate", "level": "action"},
                {"level": "notification", "uri": "/lovelace/gate"},
            ]
        },
    )
    # device is unknown to mobile_app, so gets both the iOS and Android forms
    assert data["url"] == "/lovelace/gate"
    assert data["clickAction"] == "/lovelace/gate"
    assert data["actions"] == [{"action": "OPEN_GATE", "title": "Open the gate"}]


async def test_action_group_notification_level_action(fixture: TestingContext) -> None:
    data = await _push_data(fixture, {"action_groups": ["camera_actions"], "priority": "high"})
    assert data["url"] == "homeassistant://navigate/lovelace/high"
    assert data["clickAction"] == "homeassistant://navigate/lovelace/high"
    assert data["actions"] == [{"action": "CAMERA_SILENCE", "title": "Silence"}]


async def test_action_group_templates_rendered(fixture: TestingContext) -> None:
    data = await _push_data(fixture, {"action_groups": ["alarm_actions"], "priority": "high"})
    assert data["actions"] == [{"action": "ALARM_HIGH", "title": "Alarm at high"}]


async def test_explicit_url_wins_over_notification_level_action(fixture: TestingContext) -> None:
    data = await _push_data(
        fixture, {"action_groups": ["alarm_actions"], "data": {"url": "/lovelace/own", "clickAction": "/lovelace/mine"}}
    )
    assert data["url"] == "/lovelace/own"
    assert data["clickAction"] == "/lovelace/mine"


async def test_ad_hoc_action_wins_over_action_group_and_scenario(fixture: TestingContext) -> None:
    data = await _push_data(
        fixture,
        {
            "actions": [{"level": "notification", "uri": "https://my.home/ad_hoc"}],
            "action_groups": ["camera_actions"],
            "apply_scenarios": ["alarm"],
        },
    )
    assert data["url"] == "https://my.home/ad_hoc"
    assert data["clickAction"] == "https://my.home/ad_hoc"


async def test_action_group_on_notification_wins_over_scenario(fixture: TestingContext) -> None:
    data = await _push_data(fixture, {"action_groups": ["alarm_actions"], "apply_scenarios": ["cameras"]})
    assert data["url"] == "https://my.home/alarm"


@pytest.mark.parametrize(
    ("scenarios", "expected"),
    [
        (["alarm", "cameras"], "https://my.home/alarm"),
        (["cameras", "alarm"], "homeassistant://navigate/lovelace/medium"),
    ],
)
async def test_first_scenario_wins(fixture: TestingContext, scenarios: list[str], expected: str) -> None:
    data = await _push_data(fixture, {"apply_scenarios": scenarios})
    assert data["url"] == expected
    assert data["clickAction"] == expected
    # both scenarios still supply their buttons
    assert {a["action"] for a in data["actions"]} == {"CAMERA_SILENCE", "ALARM_MEDIUM"}


async def test_ntfy_click_from_notification_level_action(fixture: TestingContext) -> None:
    fixture.hass_api.external_url = "https://my.home"
    uut = Notification(
        fixture,
        "testing 123",
        action_data={"delivery": "ntfy", "actions": [{"level": "notification", "uri": "/lovelace/gate"}]},
    )
    await uut.initialize()
    await uut.deliver()
    envelope = uut.deliveries["ntfy"][EnvelopeOutcome.SUCCESS][0]  # type:ignore[index]
    assert envelope.calls[0].action_data["click"] == "https://my.home/lovelace/gate"  # type:ignore[index,union-attr]


def test_notification_level_action_needs_uri() -> None:
    with pytest.raises(vol.Invalid, match="must have a uri or uri_template"):
        MOBILE_ACTION_SCHEMA({"level": "notification", "title": "Open"})
    assert MOBILE_ACTION_SCHEMA({"level": "notification", "uri": "https://my.home"})
    assert MOBILE_ACTION_SCHEMA({"level": "notification", "uri_template": "https://my.home/{{ x }}"})


@pytest.mark.parametrize("key", ["action", "action_template"])
def test_notification_level_action_cannot_have_action(key: str) -> None:
    with pytest.raises(vol.Invalid, match="cannot have an action"):
        MOBILE_ACTION_SCHEMA({"level": "notification", "uri": "https://my.home", key: "OPEN"})


def test_uri_and_uri_template_are_exclusive() -> None:
    with pytest.raises(vol.Invalid):
        MOBILE_ACTION_SCHEMA({"action": "OPEN", "uri": "https://my.home", "uri_template": "https://my.home/{{ x }}"})


def test_unknown_level_rejected() -> None:
    with pytest.raises(vol.Invalid):
        MOBILE_ACTION_SCHEMA({"action": "OPEN", "level": "banner"})


def test_one_notification_level_action_per_group() -> None:
    with pytest.raises(vol.Invalid, match="Only one action can be level: notification"):
        SUPERNOTIFY_YAML_SCHEMA({
            "action_groups": {
                "doubled": [
                    {"level": "notification", "uri": "https://my.home/one"},
                    {"level": "notification", "uri": "https://my.home/two"},
                ]
            }
        })


def test_ad_hoc_notification_level_action_validated() -> None:
    with pytest.raises(vol.Invalid, match="must have a uri or uri_template"):
        NOTIFY_ACTION_SCHEMA({"message": "hi", "actions": [{"level": "notification"}]})
    with pytest.raises(vol.Invalid, match="Only one action can be level: notification"):
        NOTIFY_ACTION_SCHEMA({
            "message": "hi",
            "actions": [
                {"level": "notification", "uri": "https://my.home/one"},
                {"level": "notification", "uri": "https://my.home/two"},
            ],
        })


@pytest.mark.parametrize(
    "action_data",
    [
        {"action_groups": ["silence_actions"], "media": {"camera_entity_id": "camera.porch"}},
        {"apply_scenarios": ["porch"]},
    ],
    ids=["camera_on_notification", "camera_from_scenario"],
)
async def test_camera_in_action_templates(fixture: TestingContext, action_data: dict[str, Any]) -> None:
    with patch("custom_components.supernotify.media_grab.snap_camera", return_value=None):
        data = await _push_data(fixture, action_data)
    assert {"action": "SILENCE_camera.porch", "title": "Silence Porch"} in data["actions"]


async def test_telegram_keyboard_skips_notification_level_action(caplog: pytest.LogCaptureFixture) -> None:
    keyboard = _build_inline_keyboard([
        {"action": "OPEN_GATE", "title": "Open the gate", "level": "action"},
        {"level": "notification", "uri": "https://my.home/gate"},
    ])
    assert keyboard == [[["Open the gate", "OPEN_GATE"]]]
    assert "skipped" not in caplog.text
