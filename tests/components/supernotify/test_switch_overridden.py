"""The `overridden` attribute of the scenario, recipient, delivery and transport switches: true while a
switch has been changed at runtime and no longer matches the configured `enabled`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import STATE_OFF
from homeassistant.core import State
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.supernotify import DOMAIN

from .test_switch import SWITCHES, _config, _setup, _turn

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(params=list(SWITCHES))
def kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


def _overridden(hass: HomeAssistant, entity_id: str) -> object:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.attributes["overridden"]


async def test_not_overridden_as_configured(hass: HomeAssistant) -> None:
    await _setup(hass, _config())

    for entity_id in SWITCHES.values():
        assert _overridden(hass, entity_id) is False


async def test_overridden_while_changed_by_hand(hass: HomeAssistant, kind: str) -> None:
    await _setup(hass, _config())

    await _turn(hass, SWITCHES[kind], on=False)
    assert _overridden(hass, SWITCHES[kind]) is True
    for other, entity_id in SWITCHES.items():
        if other != kind:
            assert _overridden(hass, entity_id) is False

    await _turn(hass, SWITCHES[kind], on=True)
    assert _overridden(hass, SWITCHES[kind]) is False


async def test_configured_off_and_turned_on_is_overridden(hass: HomeAssistant) -> None:
    await _setup(hass, _config({"delivery": False}))
    assert _overridden(hass, SWITCHES["delivery"]) is False

    await _turn(hass, SWITCHES["delivery"], on=True)

    assert _overridden(hass, SWITCHES["delivery"]) is True


async def test_reset_overrides_clears_it(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    for entity_id in SWITCHES.values():
        await _turn(hass, entity_id, on=False)

    await hass.services.async_call(DOMAIN, "reset_overrides", None, blocking=True)
    await hass.async_block_till_done()

    for entity_id in SWITCHES.values():
        assert _overridden(hass, entity_id) is False


async def test_restored_override_is_overridden_from_startup(hass: HomeAssistant, kind: str) -> None:
    mock_restore_cache_with_extra_data(hass, [(State(SWITCHES[kind], STATE_OFF), {"enabled": False, "config_enabled": True})])
    await _setup(hass, _config())

    assert _overridden(hass, SWITCHES[kind]) is True


async def test_item_attributes_are_kept(hass: HomeAssistant) -> None:
    await _setup(hass, _config())

    state = hass.states.get(SWITCHES["delivery"])
    assert state is not None
    assert state.attributes["transport"] == "generic"
    assert state.attributes["enabled"] is True
