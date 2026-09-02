"""Tests for the Alexa Media Player transport.

Covers:
- End-to-end delivery through Notification/Delivery/Envelope wiring, features, target selection
- _estimate_tts_duration (SSML stripping, pause chars, char_weight param)
- boolify helper (string booleans, frozenset falsy values)
- _snapshot_states (normal, playing, volume_level=None, missing entity)
- _pre_announce (media_stop ordering, pause/stop logic, idle no-op)
- _post_announce (restore, skip restore, resume music, no resume when idle,
                  no media_stop beep in post-announce)
- deliver() (no targets, no volume, volume set+restore, volume not forwarded,
             restore_volume=False, volume_fallback, exception no-block,
             music pause+resume, template resolution, wait_for_tts,
             tts_char_speed, string boolean "false" handling, atomic pre/post-announce)
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_ACTION

from custom_components.supernotify.const import CONF_TRANSPORT, TRANSPORT_ALEXA_MEDIA_PLAYER
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_media_player import (
    _BASE_DURATION,
    _CHAR_WEIGHT,
    _MUSIC_RESUME_DELAY,
    _PAUSE_WEIGHT,
    PAUSE_CHARS,
    AlexaMediaPlayerTransport,
    _estimate_tts_duration,
)
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.context import Context

DELIVERY = {
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
}


async def test_notify_alexa_media_player(uninitialized_unmocked_config: Context) -> None:
    """Test on_notify_alexa."""
    delivery_config = {
        "override": {
            CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER,
            CONF_ACTION: "notify.alexa_media_player_custom",
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._config_deliveries = delivery_config

    uut = AlexaMediaPlayerTransport(context)
    await uut.initialize()
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    notification = Notification(context, message="hello there")
    await notification.initialize()
    await uut.deliver(
        Envelope(
            Delivery("override", delivery_config["override"], uut),
            notification,
            target=Target(["media_player.hall", "media_player.toilet"]),
            data={"pause_music": False},
        )
    )
    uninitialized_unmocked_config.hass_api.call_service.assert_called_with(  # type: ignore
        "notify",
        "alexa_media_player_custom",
        service_data={
            "message": "hello there",
            "data": {"type": "announce"},
            "target": ["media_player.hall", "media_player.toilet"],
        },
        debug=False,
    )


async def test_notify_alexa_media_player_no_targets(uninitialized_unmocked_config: Context) -> None:
    delivery_config = {
        "override": {
            CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER,
            CONF_ACTION: "notify.alexa_media_player_custom",
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._config_deliveries = delivery_config

    uut = AlexaMediaPlayerTransport(context)
    await uut.initialize()
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    notification = Notification(context, message="hello there")
    await notification.initialize()
    result = await uut.deliver(
        Envelope(
            Delivery("override", delivery_config["override"], uut),
            notification,
            target=Target([]),
        )
    )
    assert result is False


async def test_notify_alexa_media_player_with_data_override(uninitialized_unmocked_config: Context) -> None:
    delivery_config = {
        "override": {
            CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER,
            CONF_ACTION: "notify.alexa_media_player_custom",
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._config_deliveries = delivery_config

    uut = AlexaMediaPlayerTransport(context)
    await uut.initialize()
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    notification = Notification(context, message="hello there")
    await notification.initialize()
    await uut.deliver(
        Envelope(
            Delivery("override", delivery_config["override"], uut),
            notification,
            target=Target(["media_player.hall"]),
            data={"type": "tts", "pause_music": False},
        )
    )
    uninitialized_unmocked_config.hass_api.call_service.assert_called_with(  # type: ignore
        "notify",
        "alexa_media_player_custom",
        service_data={
            "message": "hello there",
            "data": {"type": "tts"},
            "target": ["media_player.hall"],
        },
        debug=False,
    )


def test_alexa_media_player_features_and_validate() -> None:
    context = TestingContext(deliveries={"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER}})
    uut = AlexaMediaPlayerTransport(context, {})

    from custom_components.supernotify.model import TransportFeature

    assert uut.supported_features == TransportFeature.MESSAGE | TransportFeature.SPOKEN
    assert uut.validate_action("notify.alexa_media") is True
    assert uut.validate_action(None) is False


def test_alexa_transport_selects_targets() -> None:
    """Test on_notify_alexa."""
    context = TestingContext(deliveries={"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER}})
    uut = Delivery("unit_testing", {}, AlexaMediaPlayerTransport(context, {}))

    assert uut.select_targets(Target(["switch.alexa_1", "media_player.hall_1"])).entity_ids == ["media_player.hall_1"]


def _make_transport(states=None):
    def _get_state(entity_id):
        if not states or entity_id not in states:
            return None
        raw = states[entity_id]
        state_obj = MagicMock()
        state_obj.state = raw.get("state", "idle")
        state_obj.attributes = {k: v for k, v in raw.items() if k != "state"}
        return state_obj

    hass_api = MagicMock()
    hass_api.call_service = AsyncMock(return_value=None)
    hass_api.get_state = MagicMock(side_effect=_get_state)
    template_mock = MagicMock()
    template_mock.async_render = MagicMock(return_value="0.7")
    hass_api.template = MagicMock(return_value=template_mock)

    transport = AlexaMediaPlayerTransport.__new__(AlexaMediaPlayerTransport)
    transport.hass_api = hass_api
    transport.call_action = AsyncMock(return_value=True)
    return transport


def _make_envelope(message, data=None, entity_ids=None, condition_variables=None, delivery_options=None):
    envelope = MagicMock()
    envelope.message = message
    envelope.data = data if data is not None else {}
    envelope.target = MagicMock()
    envelope.target.entity_ids = ["media_player.ufficio"] if entity_ids is None else entity_ids
    envelope.condition_variables = condition_variables
    options = delivery_options or {}
    envelope.delivery = MagicMock()
    envelope.delivery.option_bool = MagicMock(side_effect=lambda name, default=False: bool(options.get(name, default)))
    return envelope


def _service_names(transport):
    return [c.args[1] for c in transport.hass_api.call_service.call_args_list]


class TestEstimateTtsDuration:
    def test_empty_message(self):
        assert _estimate_tts_duration("") == pytest.approx(_BASE_DURATION)

    def test_plain_text(self):
        msg = "Ciao"
        expected = _BASE_DURATION + 4 * _CHAR_WEIGHT
        assert _estimate_tts_duration(msg) == pytest.approx(expected)

    def test_pause_chars_counted(self):
        msg = "Hello. World! How, are you?"
        plain_len = len(msg)
        pause_count = sum(msg.count(p) for p in PAUSE_CHARS)
        expected = _BASE_DURATION + pause_count * _PAUSE_WEIGHT + plain_len * _CHAR_WEIGHT
        assert _estimate_tts_duration(msg) == pytest.approx(expected)

    def test_ssml_stripped(self):
        with_ssml = '<amazon:effect name="whispered">Hello world</amazon:effect>'
        plain = "Hello world"
        assert _estimate_tts_duration(with_ssml) == pytest.approx(_estimate_tts_duration(plain))

    def test_custom_char_weight(self):
        msg = "abc"
        custom = 0.10
        expected = _BASE_DURATION + 3 * custom
        assert _estimate_tts_duration(msg, char_weight=custom) == pytest.approx(expected)


class TestSnapshotStates:
    async def test_normal_volume(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.6}})
        states = await t._snapshot_states(["media_player.ufficio"], 0.5)
        assert states["media_player.ufficio"]["volume"] == pytest.approx(0.6)
        assert states["media_player.ufficio"]["playing"] is False

    async def test_playing_device(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.3}})
        states = await t._snapshot_states(["media_player.sala"], 0.5)
        assert states["media_player.sala"]["playing"] is True

    async def test_volume_none_uses_fallback(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": None}})
        states = await t._snapshot_states(["media_player.ufficio"], 0.42)
        assert states["media_player.ufficio"]["volume"] == pytest.approx(0.42)

    async def test_missing_entity_skipped(self):
        t = _make_transport()
        states = await t._snapshot_states(["media_player.ghost"], 0.5)
        assert "media_player.ghost" not in states


class TestPreAnnounce:
    async def test_idle_device_no_stop_no_pause(self):
        """media_stop must NOT be called on idle devices — triggers a beep."""
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.3, "playing": False}}
        await t._pre_announce(states, 0.9, pause_music=True)
        names = _service_names(t)
        assert "media_stop" not in names
        assert "media_pause" not in names
        assert "volume_set" in names

    async def test_playing_pause_music_true_uses_media_pause_only(self):
        """pause_music=True + playing: media_pause only, no media_stop."""
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": True}}
        await t._pre_announce(states, 0.8, pause_music=True)
        names = _service_names(t)
        assert "media_pause" in names
        assert "media_stop" not in names

    async def test_playing_pause_music_false_uses_media_stop(self):
        """pause_music=False + playing: media_stop only."""
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": True}}
        await t._pre_announce(states, 0.8, pause_music=False)
        names = _service_names(t)
        assert "media_stop" in names
        assert "media_pause" not in names

    async def test_volume_set_on_all_devices(self):
        t = _make_transport()
        states = {
            "media_player.ufficio": {"volume": 0.3, "playing": False},
            "media_player.sala": {"volume": 0.5, "playing": False},
        }
        await t._pre_announce(states, 0.8, pause_music=True)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 2
        for vc in vol_calls:
            assert vc.kwargs["service_data"]["volume_level"] == pytest.approx(0.8)

    async def test_runs_devices_concurrently(self):
        """Each Alexa cloud call can take seconds; per-device work must overlap rather than
        stack sequentially, or a handful of targets turns into a multi-second pileup."""
        t = _make_transport()
        call_delay = 0.2
        states = {f"media_player.d{i}": {"volume": 0.5, "playing": True} for i in range(5)}

        async def _delayed_call(*args, **kwargs):
            await asyncio.sleep(call_delay)

        t.hass_api.call_service = AsyncMock(side_effect=_delayed_call)
        start = time.perf_counter()
        await t._pre_announce(states, 0.8, pause_music=True)
        elapsed = time.perf_counter() - start
        assert elapsed < call_delay * len(states)


class TestPostAnnounce:
    async def test_no_media_stop_in_post_announce(self):
        """media_stop must NOT be called after TTS — Alexa is already idle."""
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.35, "playing": False}}
        await t._post_announce(states, restore_volume=True, pause_music=True)
        assert "media_stop" not in _service_names(t)

    async def test_restores_volume(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.35, "playing": False}}
        await t._post_announce(states, restore_volume=True, pause_music=True)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 1
        assert vol_calls[0].kwargs["service_data"]["volume_level"] == pytest.approx(0.35)

    async def test_skips_restore_when_disabled(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.35, "playing": False}}
        await t._post_announce(states, restore_volume=False, pause_music=True)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 0

    async def test_resumes_music_after_delay(self):
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": True}}
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t._post_announce(states, restore_volume=True, pause_music=True)
            mock_sleep.assert_awaited_once_with(_MUSIC_RESUME_DELAY)
        assert "media_play" in _service_names(t)

    async def test_no_resume_when_was_not_playing(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.5, "playing": False}}
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t._post_announce(states, restore_volume=True, pause_music=True)
            mock_sleep.assert_not_awaited()

    async def test_runs_volume_restore_concurrently(self):
        """Volume restore across devices must overlap, not stack sequential cloud round trips."""
        t = _make_transport()
        call_delay = 0.2
        states = {f"media_player.d{i}": {"volume": 0.5, "playing": False} for i in range(5)}

        async def _delayed_call(*args, **kwargs):
            await asyncio.sleep(call_delay)

        t.hass_api.call_service = AsyncMock(side_effect=_delayed_call)
        start = time.perf_counter()
        await t._post_announce(states, restore_volume=True, pause_music=True)
        elapsed = time.perf_counter() - start
        assert elapsed < call_delay * len(states)
        assert "media_play" not in _service_names(t)


class TestDeliver:
    async def test_no_targets_returns_false(self):
        t = _make_transport()
        envelope = _make_envelope("Test", entity_ids=[])
        assert await t.deliver(envelope) is False

    async def test_no_volume_no_volume_set(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle"}})
        envelope = _make_envelope("Test", data={})
        result = await t.deliver(envelope)
        assert result is True
        assert "volume_set" not in _service_names(t)

    async def test_volume_set_and_restored(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.4}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "type": "announce"})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            result = await t.deliver(envelope)
        assert result is True
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.9) in levels
        assert pytest.approx(0.4) in levels

    async def test_volume_not_forwarded_to_alexa(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        envelope = _make_envelope("Test", data={"volume": 0.8, "type": "announce"})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        action_data = t.call_action.call_args.kwargs.get("action_data", {})
        assert "volume" not in action_data.get("data", {})
        assert "volume_template" not in action_data.get("data", {})

    async def test_restore_volume_false(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.4}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "restore_volume": False})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 1

    async def test_restore_volume_string_false(self):
        """restore_volume: 'false' (YAML string) must be treated as False."""
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.4}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "restore_volume": "false"})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 1

    async def test_pause_music_string_false(self):
        """pause_music: 'false' (YAML string) must be treated as False."""
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope("Test", data={"volume": 0.8, "pause_music": "false"}, entity_ids=["media_player.sala"])
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        assert "media_pause" not in _service_names(t)

    async def test_volume_fallback_restored(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": None}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "volume_fallback": 0.55})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.55) in levels

    async def test_service_exception_does_not_block(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        t.hass_api.call_service = AsyncMock(side_effect=Exception("offline"))
        envelope = _make_envelope("Test", data={"volume": 0.8})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            result = await t.deliver(envelope)
        assert result is True

    async def test_music_paused_and_resumed(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5, "pause_music": True}})
        envelope = _make_envelope("Test", data={"volume": 0.8}, entity_ids=["media_player.sala"])
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        names = _service_names(t)
        assert "media_pause" in names
        assert "media_play" in names

    async def test_volume_template_resolved(self):
        """Jinja2 volume template must be resolved to float before volume_set."""
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.3}})
        t.hass_api.template.return_value.async_render.return_value = "0.65"
        envelope = _make_envelope(
            "Test", data={"volume": "{{ (states('input_number.notifier_morning_volume') | float(40)) / 100 }}"}
        )
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.65) in levels

    async def test_invalid_volume_template_ignored(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.3}})
        t.hass_api.template.return_value.async_render.side_effect = Exception("template error")
        envelope = _make_envelope("Test", data={"volume": "{{ invalid }}"})
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            result = await t.deliver(envelope)
        assert result is True
        assert "volume_set" not in _service_names(t)

    async def test_wait_for_tts_blocks(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        envelope = _make_envelope("Ciao", data={"wait_for_tts": True})
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t.deliver(envelope)
            mock_sleep.assert_awaited_once()
            assert mock_sleep.call_args.args[0] >= _BASE_DURATION

    async def test_wait_for_tts_false_no_sleep_without_volume(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle"}})
        envelope = _make_envelope("Ciao", data={"pause_music": False})
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t.deliver(envelope)
            mock_sleep.assert_not_awaited()

    async def test_tts_char_speed_affects_duration(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        msg = "abc"
        fast_speed = 0.001
        envelope = _make_envelope(msg, data={"wait_for_tts": True, "tts_char_speed": fast_speed})
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t.deliver(envelope)
            duration = mock_sleep.call_args.args[0]
        expected = _BASE_DURATION + 3 * fast_speed
        assert duration == pytest.approx(expected, rel=0.01)

    async def test_announce_only_delivery_default(self):
        """A delivery config's `options: {announce_only: true}` sets the default for every
        notification through that delivery, without needing per-call data."""
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope(
            "Test",
            data={},
            entity_ids=["media_player.sala"],
            delivery_options={"media_auto_pause": False},
        )
        await t.deliver(envelope)
        names = _service_names(t)
        assert "media_pause" not in names
        assert "volume_set" not in names

    async def test_auto_pause_false_with_requested_volume(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope(
            "Test",
            data={"volume": 0.3},
            entity_ids=["media_player.sala"],
            delivery_options={"media_auto_pause": False},
        )
        result = await t.deliver(envelope)
        assert result is True
        names = _service_names(t)
        assert "media_pause" not in names
        assert "volume_set" not in names

    async def test_wait_for_tts_honoured_with_auto_pause_disabled(self):
        t = _make_transport({"media_player.sala": {"state": "idle"}})
        envelope = _make_envelope(
            "Ciao",
            data={"wait_for_tts": True},
            entity_ids=["media_player.sala"],
            delivery_options={"media_auto_pause": False},
        )
        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await t.deliver(envelope)
            mock_sleep.assert_awaited_once()
            assert mock_sleep.call_args.args[0] >= _BASE_DURATION
        names = _service_names(t)
        assert "media_pause" not in names
        assert "volume_set" not in names

    async def test_music_unpauses_after_empty_message(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope("", data={"volume": 0.9}, entity_ids=["media_player.sala"])
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        names = _service_names(t)
        assert "media_pause" in names
        assert "media_play" in names
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.9) in levels
        assert pytest.approx(0.5) in levels

    async def test_post_announce_runs_even_if_call_action_fails(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        t.call_action = AsyncMock(side_effect=RuntimeError("boom"))
        envelope = _make_envelope("Test", data={"volume": 0.9}, entity_ids=["media_player.sala"])
        with patch("custom_components.supernotify.transports.alexa_media_player.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError):
                await t.deliver(envelope)
        names = _service_names(t)
        assert "media_pause" in names
        assert "media_play" in names
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.9) in levels
        assert pytest.approx(0.5) in levels

    async def test_post_announce_runs_when_tts_wait_is_cancelled(self):
        """Regression test: task cancellation during the TTS wait (e.g. Home Assistant
        shutting down mid-delivery) must still trigger the restore/resume rather than leaving
        the device stuck paused/at announcement volume. CancelledError must still propagate."""
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope("Test", data={"volume": 0.9}, entity_ids=["media_player.sala"])

        call_count = 0

        async def _sleep_side_effect(_duration):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First sleep is the TTS wait; cancel it. The second (music resume delay,
                # inside _post_announce) must still be reached and complete normally.
                raise asyncio.CancelledError()

        with patch(
            "custom_components.supernotify.transports.alexa_media_player.asyncio.sleep",
            side_effect=_sleep_side_effect,
        ):
            with pytest.raises(asyncio.CancelledError):
                await t.deliver(envelope)
        names = _service_names(t)
        assert "media_pause" in names
        assert "media_play" in names
        vol_calls = [c for c in t.hass_api.call_service.call_args_list if c.args[1] == "volume_set"]
        levels = [c.kwargs["service_data"]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.9) in levels
        assert pytest.approx(0.5) in levels
