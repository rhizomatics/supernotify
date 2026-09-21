"""Tests for supernotify.reset_overrides: everything switched on or off at runtime is put back
to its configured enabled state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as er

from custom_components.supernotify import DOMAIN

from .test_switch import SWITCHES, _config, _model, _preexisting_binary_sensors, _reload, _setup, _state, _turn

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _reset(hass: HomeAssistant, data: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await hass.services.async_call(DOMAIN, "reset_overrides", data, blocking=True, return_response=True)
    await hass.async_block_till_done()
    assert response is not None
    return dict(response)


@pytest.mark.parametrize("kind", list(SWITCHES))
async def test_reset_one_kind(hass: HomeAssistant, kind: str) -> None:
    engine = await _setup(hass, _config())
    for entity_id in SWITCHES.values():
        await _turn(hass, entity_id, on=False)

    response = await _reset(hass, {"kind": kind})

    assert response == {"reset": {kind: [_model(engine, kind).name]}}
    assert _model(engine, kind).enabled is True
    assert _state(hass, SWITCHES[kind]) == STATE_ON
    for other_kind, entity_id in SWITCHES.items():
        if other_kind != kind:
            assert _state(hass, entity_id) == STATE_OFF


async def test_reset_all_kinds(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config({"delivery": False}))
    await _turn(hass, SWITCHES["scenario"], on=False)
    await _turn(hass, SWITCHES["delivery"], on=True)

    response = await _reset(hass)

    assert response == {"reset": {"scenario": ["sera"], "recipient": [], "delivery": ["testing"], "transport": []}}
    assert _model(engine, "scenario").enabled is True
    assert _model(engine, "delivery").enabled is False
    assert _state(hass, SWITCHES["delivery"]) == STATE_OFF


async def test_reset_with_no_overrides_resets_nothing(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    before = hass.states.get(SWITCHES["scenario"])

    response = await _reset(hass, {"kind": "scenario"})

    assert response == {"reset": {"scenario": []}}
    assert hass.states.get(SWITCHES["scenario"]) == before


async def test_reset_rejects_unknown_kind(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "reset_overrides", {"kind": "camera"}, blocking=True)


async def test_reset_without_response(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    await _turn(hass, SWITCHES["recipient"], on=False)

    assert await hass.services.async_call(DOMAIN, "reset_overrides", None, blocking=True) is None
    assert _model(engine, "recipient").enabled is True


async def test_reset_refreshes_related_binary_sensors(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", "recipient_joe")
    await _setup(hass, _config())
    for kind in ("scenario", "recipient", "delivery"):
        await _turn(hass, SWITCHES[kind], on=False)
    assert _state(hass, "binary_sensor.supernotify_scenario_sera") == STATE_OFF

    await _reset(hass)

    assert _state(hass, "binary_sensor.supernotify_scenario_sera") == STATE_ON
    assert _state(hass, "binary_sensor.supernotify_recipient_joe") == STATE_ON
    assert _state(hass, "binary_sensor.supernotify_delivery_testing") == STATE_ON


@pytest.mark.parametrize("kind", list(SWITCHES))
async def test_reset_includes_one_whose_switch_is_disabled(hass: HomeAssistant, kind: str) -> None:
    """Reset from the scenario, recipient, delivery or transport itself, with the binary_sensor
    following it re-published, as the switch would have done."""
    unique_id = SWITCHES[kind].removeprefix("switch.supernotify_")
    er.async_get(hass).async_get_or_create(
        "switch",
        DOMAIN,
        unique_id,
        suggested_object_id=SWITCHES[kind].removeprefix("switch."),
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    _preexisting_binary_sensors(hass, "recipient_joe", "delivery_testing", "transport_generic")
    engine = await _setup(hass, _config())
    assert unique_id not in engine.override_switches
    _model(engine, kind).enabled = False
    # as last published while it was off
    hass.states.async_set(f"binary_sensor.supernotify_{unique_id}", STATE_OFF)

    response = await _reset(hass, {"kind": kind})

    assert response == {"reset": {kind: [_model(engine, kind).name]}}
    assert _model(engine, kind).enabled is True
    assert _state(hass, f"binary_sensor.supernotify_{unique_id}") == STATE_ON


async def test_disabled_switch_keeps_its_override_dormant(hass: HomeAssistant) -> None:
    """An override belongs to its switch: with the switch disabled in the entity registry the
    configuration applies, reset_overrides has nothing to reset, and the override is back once
    the switch is enabled again - when it can be reset as usual."""
    registry = er.async_get(hass)
    await _setup(hass, _config())
    await _turn(hass, SWITCHES["delivery"], on=False)

    registry.async_update_entity(SWITCHES["delivery"], disabled_by=er.RegistryEntryDisabler.USER)
    engine = await _reload(hass)
    assert _model(engine, "delivery").enabled is True
    assert await _reset(hass, {"kind": "delivery"}) == {"reset": {"delivery": []}}

    registry.async_update_entity(SWITCHES["delivery"], disabled_by=None)
    engine = await _reload(hass)
    assert _model(engine, "delivery").enabled is False
    assert _state(hass, SWITCHES["delivery"]) == STATE_OFF

    assert await _reset(hass, {"kind": "delivery"}) == {"reset": {"delivery": ["testing"]}}
    assert _state(hass, SWITCHES["delivery"]) == STATE_ON


async def test_reset_then_reload_does_not_restore_override(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    await _turn(hass, SWITCHES["transport"], on=False)
    await _reset(hass)

    engine = await _reload(hass)

    assert _model(engine, "transport").enabled is True
    assert _state(hass, SWITCHES["transport"]) == STATE_ON


# --- Reset overrides button ------------------------------------------------------------------


async def test_button_resets_all_kinds(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    for entity_id in SWITCHES.values():
        await _turn(hass, entity_id, on=False)

    await hass.services.async_call("button", "press", {"entity_id": "button.supernotify_reset_overrides"}, blocking=True)
    await hass.async_block_till_done()

    for kind, entity_id in SWITCHES.items():
        assert _model(engine, kind).enabled is True
        assert _state(hass, entity_id) == STATE_ON


async def test_button_is_on_the_supernotify_device(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    reg_entry = er.async_get(hass).async_get("button.supernotify_reset_overrides")
    assert reg_entry is not None
    assert reg_entry.unique_id == "reset_overrides"
    assert reg_entry.config_entry_id == entry.entry_id
    assert reg_entry.device_id is not None
    state = hass.states.get("button.supernotify_reset_overrides")
    assert state is not None
    assert state.name == "SuperNotify Reset overrides"
