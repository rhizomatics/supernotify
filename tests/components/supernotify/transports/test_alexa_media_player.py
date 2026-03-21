"""Tests for the Alexa Media Player transport volume management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.supernotify.transports.alexa_media_player import (
    _BASE_DURATION,
    _CHAR_WEIGHT,
    _MUSIC_RESUME_DELAY,
    _PAUSE_WEIGHT,
    PAUSE_CHARS,
    AlexaMediaPlayerTransport,
    _estimate_tts_duration,
)


def _make_transport(states=None):
    hass = MagicMock()
    hass.services.async_call = AsyncMock(return_value=None)

    def _get_state(entity_id):
        if not states or entity_id not in states:
            return None
        raw = states[entity_id]
        state_obj = MagicMock()
        state_obj.state = raw.get("state", "idle")
        state_obj.attributes = {k: v for k, v in raw.items() if k != "state"}
        return state_obj

    hass.states.get = MagicMock(side_effect=_get_state)
    transport = AlexaMediaPlayerTransport.__new__(AlexaMediaPlayerTransport)
    transport.hass = hass
    transport.call_action = AsyncMock(return_value=True)
    return transport


def _make_envelope(message, data=None, entity_ids=None):
    envelope = MagicMock()
    envelope.message = message
    envelope.data = {"data": data} if data else {}
    envelope.target = MagicMock()
    envelope.target.entity_ids = entity_ids or ["media_player.ufficio"]
    return envelope


class TestEstimateTtsDuration:
    def test_empty_message(self):
        assert _estimate_tts_duration("") == _BASE_DURATION

    def test_plain_text(self):
        msg = "Ciao"
        expected = _BASE_DURATION + 4 * _CHAR_WEIGHT
        assert abs(_estimate_tts_duration(msg) - expected) < 0.01

    def test_pause_chars_counted(self):
        msg = "Hello. World! How, are you?"
        plain_len = len(msg)
        pause_count = sum(msg.count(p) for p in PAUSE_CHARS)
        expected = _BASE_DURATION + pause_count * _PAUSE_WEIGHT + plain_len * _CHAR_WEIGHT
        assert abs(_estimate_tts_duration(msg) - expected) < 0.01

    def test_ssml_stripped(self):
        with_ssml = '<amazon:effect name="whispered">Hello world</amazon:effect>'
        plain = "Hello world"
        assert abs(_estimate_tts_duration(with_ssml) - _estimate_tts_duration(plain)) < 0.01

    def test_prosody_stripped(self):
        msg = '<speak><prosody volume="x-loud">Test.</prosody></speak>'
        assert abs(_estimate_tts_duration(msg) - _estimate_tts_duration("Test.")) < 0.01


class TestSnapshotStates:
    @pytest.mark.asyncio
    async def test_normal_volume(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.6}})
        states = await t._snapshot_states(["media_player.ufficio"], 0.5)
        assert states["media_player.ufficio"]["volume"] == pytest.approx(0.6)
        assert states["media_player.ufficio"]["playing"] is False

    @pytest.mark.asyncio
    async def test_playing_device(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.3}})
        states = await t._snapshot_states(["media_player.sala"], 0.5)
        assert states["media_player.sala"]["playing"] is True

    @pytest.mark.asyncio
    async def test_volume_none_uses_fallback(self):
        """Covers AMP issue #1394: volume_level is None at HA startup."""
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": None}})
        states = await t._snapshot_states(["media_player.ufficio"], 0.42)
        assert states["media_player.ufficio"]["volume"] == pytest.approx(0.42)

    @pytest.mark.asyncio
    async def test_missing_entity_skipped(self):
        t = _make_transport()
        states = await t._snapshot_states(["media_player.ghost"], 0.5)
        assert "media_player.ghost" not in states


class TestPreAnnounce:
    @pytest.mark.asyncio
    async def test_media_stop_before_volume_set(self):
        """media_stop must precede volume_set to suppress Alexa beep."""
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.3, "playing": False}}
        await t._pre_announce(states, 0.9, False)
        calls = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert calls.index("media_stop") < calls.index("volume_set")

    @pytest.mark.asyncio
    async def test_pauses_music_when_playing(self):
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": True}}
        await t._pre_announce(states, 0.8, True)
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "media_pause" in names

    @pytest.mark.asyncio
    async def test_no_pause_when_not_playing(self):
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": False}}
        await t._pre_announce(states, 0.8, True)
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "media_pause" not in names

    @pytest.mark.asyncio
    async def test_volume_set_on_all_devices(self):
        t = _make_transport()
        states = {
            "media_player.ufficio": {"volume": 0.3, "playing": False},
            "media_player.sala": {"volume": 0.5, "playing": False},
        }
        await t._pre_announce(states, 0.8, True)
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 2
        for vc in vol_calls:
            assert vc.args[2]["volume_level"] == pytest.approx(0.8)


class TestPostAnnounce:
    @pytest.mark.asyncio
    async def test_restores_volume(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.35, "playing": False}}
        await t._post_announce(states, True, True)
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 1
        assert vol_calls[0].args[2]["volume_level"] == pytest.approx(0.35)

    @pytest.mark.asyncio
    async def test_skips_restore_when_disabled(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.35, "playing": False}}
        await t._post_announce(states, False, True)
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 0

    @pytest.mark.asyncio
    async def test_resumes_music_after_delay(self):
        t = _make_transport()
        states = {"media_player.sala": {"volume": 0.5, "playing": True}}
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await t._post_announce(states, True, True)
            mock_sleep.assert_awaited_with(_MUSIC_RESUME_DELAY)
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "media_play" in names

    @pytest.mark.asyncio
    async def test_no_resume_when_was_not_playing(self):
        t = _make_transport()
        states = {"media_player.ufficio": {"volume": 0.5, "playing": False}}
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await t._post_announce(states, True, True)
            mock_sleep.assert_not_awaited()
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "media_play" not in names


class TestDeliver:
    @pytest.mark.asyncio
    async def test_no_targets_returns_false(self):
        t = _make_transport()
        envelope = _make_envelope("Test", entity_ids=[])
        assert await t.deliver(envelope) is False

    @pytest.mark.asyncio
    async def test_no_volume_no_service_calls(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        envelope = _make_envelope("Test")
        result = await t.deliver(envelope)
        assert result is True
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "volume_set" not in names

    @pytest.mark.asyncio
    async def test_volume_set_and_restored(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.4}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "type": "announce"})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await t.deliver(envelope)
        assert result is True
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        levels = [c.args[2]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.9) in levels
        assert pytest.approx(0.4) in levels

    @pytest.mark.asyncio
    async def test_volume_not_forwarded_to_alexa(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        envelope = _make_envelope("Test", data={"volume": 0.8, "type": "announce"})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        action_data = t.call_action.call_args.kwargs.get("action_data", {})
        assert "volume" not in action_data.get("data", {})

    @pytest.mark.asyncio
    async def test_restore_volume_false(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.4}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "restore_volume": False})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        assert len(vol_calls) == 1
        assert vol_calls[0].args[2]["volume_level"] == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_volume_fallback_restored(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": None}})
        envelope = _make_envelope("Test", data={"volume": 0.9, "volume_fallback": 0.55})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        vol_calls = [c for c in t.hass.services.async_call.call_args_list if c.args[1] == "volume_set"]
        levels = [c.args[2]["volume_level"] for c in vol_calls]
        assert pytest.approx(0.55) in levels

    @pytest.mark.asyncio
    async def test_service_exception_does_not_block(self):
        t = _make_transport({"media_player.ufficio": {"state": "idle", "volume_level": 0.5}})
        t.hass.services.async_call = AsyncMock(side_effect=Exception("offline"))
        envelope = _make_envelope("Test", data={"volume": 0.8})
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await t.deliver(envelope)
        assert result is True

    @pytest.mark.asyncio
    async def test_music_paused_and_resumed(self):
        t = _make_transport({"media_player.sala": {"state": "playing", "volume_level": 0.5}})
        envelope = _make_envelope("Test", data={"volume": 0.8}, entity_ids=["media_player.sala"])
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await t.deliver(envelope)
        names = [c.args[1] for c in t.hass.services.async_call.call_args_list]
        assert "media_pause" in names
        assert "media_play" in names
