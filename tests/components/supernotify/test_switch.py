"""Tests for the switches overriding a configured enabled flag (switch.py): the override is kept
across a restart or reload for as long as the configured value it overrides is unchanged."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import State
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import mock_restore_cache, mock_restore_cache_with_extra_data

from custom_components.supernotify import CONFIG_SCHEMA, DOMAIN, KEY_YAML_CONFIG
from custom_components.supernotify.switch import OverrideStoredData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.engine import SupernotifyEngine
    from custom_components.supernotify.switch import Overridable

# kind -> entity_id of its switch in the config built by _config()
SWITCHES: dict[str, str] = {
    "scenario": "switch.supernotify_scenario_sera",
    "recipient": "switch.supernotify_recipient_joe",
}


def _config(enabled: dict[str, bool] | None = None) -> dict[str, Any]:
    """One of each kind of overridable thing, with `enabled:` configured for the given kinds."""
    enabled = enabled or {}
    delivery: dict[str, Any] = {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"}
    scenario: dict[str, Any] = {
        "alias": "Evening mode",
        "conditions": {"condition": "state", "entity_id": "binary_sensor.dnd_test", "state": "on"},
        "delivery": {"testing": {}},
    }
    recipient: dict[str, Any] = {"person": "person.joe", "alias": "Joe Bloggs"}
    if "scenario" in enabled:
        scenario["enabled"] = enabled["scenario"]
    if "recipient" in enabled:
        recipient["enabled"] = enabled["recipient"]
    if "delivery" in enabled:
        delivery["enabled"] = enabled["delivery"]
    config: dict[str, Any] = {"delivery": {"testing": delivery}, "scenarios": {"sera": scenario}, "recipients": [recipient]}
    if "transport" in enabled:
        config["transports"] = {"generic": {"enabled": enabled["transport"]}}
    return config


def _model(engine: SupernotifyEngine, kind: str) -> Overridable:
    context = engine.context
    models: dict[str, Overridable] = {
        "scenario": context.scenario_registry.scenarios["sera"],
        "recipient": context.people_registry.people["person.joe"],
    }
    if "delivery" in SWITCHES:
        models["delivery"] = context.delivery_registry.deliveries["testing"]
        models["transport"] = context.delivery_registry.transports["generic"]
    return models[kind]


async def _setup(hass: HomeAssistant, config: dict[str, Any]) -> SupernotifyEngine:
    hass.states.async_set("binary_sensor.dnd_test", "on")
    hass.states.async_set("person.joe", "home")
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data


async def _reload(hass: HomeAssistant, config: dict[str, Any] | None = None) -> SupernotifyEngine:
    """Reload the config entry, optionally with changed YAML, as supernotify.reload would."""
    if config is not None:
        hass.data[DOMAIN][KEY_YAML_CONFIG] = CONFIG_SCHEMA({DOMAIN: config})[DOMAIN]
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


async def _turn(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    await hass.services.async_call("switch", "turn_on" if on else "turn_off", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()


@pytest.fixture(params=list(SWITCHES))
def kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


async def test_restore_applies_override_when_config_unchanged(hass: HomeAssistant, kind: str) -> None:
    mock_restore_cache_with_extra_data(hass, [(State(SWITCHES[kind], STATE_OFF), {"enabled": False, "config_enabled": True})])
    engine = await _setup(hass, _config())

    assert _model(engine, kind).enabled is False
    assert _model(engine, kind).config_enabled is True
    assert _state(hass, SWITCHES[kind]) == STATE_OFF


async def test_restore_ignored_when_config_changed(hass: HomeAssistant, kind: str) -> None:
    # stored while configured off, but now configured on - the configuration wins
    mock_restore_cache_with_extra_data(hass, [(State(SWITCHES[kind], STATE_OFF), {"enabled": False, "config_enabled": False})])
    engine = await _setup(hass, _config({kind: True}))

    assert _model(engine, kind).enabled is True
    assert _state(hass, SWITCHES[kind]) == STATE_ON


@pytest.mark.parametrize(
    "extra_data",
    [{}, {"enabled": False}, {"enabled": "off", "config_enabled": True}, {"enabled": False, "config_enabled": 1}],
)
async def test_restore_ignores_malformed_extra_data(hass: HomeAssistant, kind: str, extra_data: dict[str, Any]) -> None:
    mock_restore_cache_with_extra_data(hass, [(State(SWITCHES[kind], STATE_OFF), extra_data)])
    engine = await _setup(hass, _config())

    assert _model(engine, kind).enabled is True
    assert _state(hass, SWITCHES[kind]) == STATE_ON


async def test_no_extra_data_uses_config(hass: HomeAssistant, kind: str) -> None:
    # a last state alone, e.g. from before overrides were kept, is not an override
    mock_restore_cache(hass, [State(SWITCHES[kind], STATE_OFF)])
    engine = await _setup(hass, _config())

    assert _model(engine, kind).enabled is True
    assert _state(hass, SWITCHES[kind]) == STATE_ON


async def test_reload_keeps_override(hass: HomeAssistant, kind: str) -> None:
    await _setup(hass, _config())
    await _turn(hass, SWITCHES[kind], on=False)

    engine = await _reload(hass)

    assert _model(engine, kind).enabled is False
    assert _state(hass, SWITCHES[kind]) == STATE_OFF


async def test_reload_after_config_change_drops_override(hass: HomeAssistant, kind: str) -> None:
    await _setup(hass, _config({kind: False}))
    await _turn(hass, SWITCHES[kind], on=True)

    engine = await _reload(hass, _config({kind: True}))
    assert _model(engine, kind).enabled is True
    # the earlier override is gone: configured off again, it is off
    engine = await _reload(hass, _config({kind: False}))
    assert _model(engine, kind).enabled is False
    assert _state(hass, SWITCHES[kind]) == STATE_OFF


async def test_extra_restore_state_data_round_trip(hass: HomeAssistant, kind: str) -> None:
    engine = await _setup(hass, _config())
    await _turn(hass, SWITCHES[kind], on=False)

    switch = next(s for s in engine.override_switches.values() if s.entity_id == SWITCHES[kind])
    data = switch.extra_restore_state_data
    assert data == OverrideStoredData(enabled=False, config_enabled=True)
    assert OverrideStoredData.from_dict(data.as_dict()) == data


async def test_switches_are_registered_with_the_engine_until_unloaded(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    assert {s.entity_id for s in engine.override_switches.values()} == set(SWITCHES.values())
    assert all(key == switch.unique_id for key, switch in engine.override_switches.items())

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert engine.override_switches == {}


async def test_restore_refreshes_scenario_binary_sensor(hass: HomeAssistant) -> None:
    """The conditions hold, but a scenario restored as disabled has its condition state off."""
    mock_restore_cache_with_extra_data(
        hass, [(State(SWITCHES["scenario"], STATE_OFF), {"enabled": False, "config_enabled": True})]
    )
    await _setup(hass, _config())

    assert _state(hass, "binary_sensor.supernotify_scenario_sera") == STATE_OFF


async def test_noop_toggle_writes_nothing(hass: HomeAssistant, kind: str) -> None:
    engine = await _setup(hass, _config())

    switch = next(s for s in engine.override_switches.values() if s.entity_id == SWITCHES[kind])
    with patch.object(switch, "async_write_ha_state", wraps=switch.async_write_ha_state) as write:
        assert switch.async_set_enabled(True) is False
        await _turn(hass, SWITCHES[kind], on=True)
        write.assert_not_called()

        assert switch.async_set_enabled(False) is True
        write.assert_called_once()
    assert _state(hass, SWITCHES[kind]) == STATE_OFF
