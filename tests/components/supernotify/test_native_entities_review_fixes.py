"""Regression tests for the multi-agent review of feat/native-entities-scenario-recipient-
counters (2026-09-08), run before proposing the branch upstream as a PR.

Covers the three confirmed high-severity bugs:
  1. counter restore race (notify.py restore_sent/restore_failures overwriting a higher
     in-memory value with an older persisted one - see restore_sent()'s docstring)
  2. scenario auto-disabled at boot (scenario.py handle_entity_state_change mistaking a
     stateful scenario's own first published state - which reflects condition evaluation, not
     `enabled` - for someone manually disabling it)
  3. manual re-enable self-cancelling in the same tick (an entity.async_write_ha_state() call
     right after re-enabling used to immediately re-evaluate conditions, still false, and flip
     `enabled` back off before the toggle was ever visible)

and the confirmed medium-severity bug: determine_occupancy() recomputed once per scenario in
a batch refresh instead of once for the whole batch.

The six events exercised end-to-end below (boot with a false condition, boot with a true
condition, manual disable, manual re-enable, config entry reload, and a multi-scenario batch
refresh) are the "tutti e sei gli eventi" debug pass requested after applying these fixes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.engine import SupernotifyEngine
from custom_components.supernotify.scenario import ScenarioRegistry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _setup_supernotify(hass: HomeAssistant, config: dict) -> SupernotifyEngine:
    """Same helper as test_config_yaml.py: bootstrap supernotify from a top-level
    `supernotify:` YAML config and return the live service."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return entry.runtime_data


def _stateful_scenario_config(condition_state: str) -> dict:
    """A scenario gated on a real entity - unlike the transient/manual scenarios used
    elsewhere in the test suite, this is the shape that actually exercises the boot/toggle
    mechanism the review found buggy (see module docstring)."""
    return {
        "delivery": {
            "testing": {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"},
        },
        "scenarios": {
            "sera": {
                "alias": "Evening mode",
                "conditions": {"condition": "state", "entity_id": "binary_sensor.dnd_test", "state": condition_state},
                "delivery": {"testing": {}},
            },
        },
        "recipients": [],
    }


# --- Bug #1: counter restore race -----------------------------------------------------------


def test_restore_sent_does_not_regress_a_higher_in_memory_value() -> None:
    """A notification landing on the raw fallback counter (see async_send_message) during the
    window between async_register_services() and the sensor platform's restore must not be
    silently erased by a restore() call carrying the older, pre-increment value."""
    action = MagicMock()
    action.sent = 5
    SupernotifyEngine.restore_sent(action, 2)
    assert action.sent == 5


def test_restore_sent_applies_the_restored_value_when_higher() -> None:
    """The normal case: nothing incremented the fallback yet, so the restored value wins."""
    action = MagicMock()
    action.sent = 0
    SupernotifyEngine.restore_sent(action, 7)
    assert action.sent == 7


def test_restore_failures_does_not_regress_a_higher_in_memory_value() -> None:
    action = MagicMock()
    action.failures = 3
    SupernotifyEngine.restore_failures(action, 1)
    assert action.failures == 3


def test_restore_failures_applies_the_restored_value_when_higher() -> None:
    action = MagicMock()
    action.failures = 0
    SupernotifyEngine.restore_failures(action, 4)
    assert action.failures == 4


# --- Bug #2: scenario auto-disabled at boot --------------------------------------------------


async def test_stateful_scenario_survives_its_own_first_state_publish(hass: HomeAssistant) -> None:
    """A scenario with entity-backed conditions that evaluate False at boot (dnd_test is
    "off", condition wants "on") must stay `enabled` after setup - the entity's own first
    published state (OFF, since the condition is false) must not be mistaken by
    handle_entity_state_change for a manual disable."""
    hass.states.async_set("binary_sensor.dnd_test", "off")
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    scenario = entry.runtime_data.context.scenario_registry.scenarios["sera"]
    assert scenario.enabled is True
    # and the published state does reflect the (false) condition, proving this isn't just an
    # untouched entity - the mechanism ran, it just correctly left `enabled` alone.
    state = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert state is not None
    assert state.state == STATE_OFF


async def test_stateful_scenario_survives_first_publish_when_true_at_boot(hass: HomeAssistant) -> None:
    """Symmetric case: a condition that is already True at boot must also leave `enabled`
    untouched (the suppression is unconditional on the first publish, not state-dependent)."""
    hass.states.async_set("binary_sensor.dnd_test", "on")
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    scenario = entry.runtime_data.context.scenario_registry.scenarios["sera"]
    assert scenario.enabled is True
    state = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert state is not None
    assert state.state == STATE_ON


async def test_scenario_survives_config_entry_reload(hass: HomeAssistant) -> None:
    """A config entry reload (e.g. after an options change) tears down and recreates the
    scenario entities from scratch - register_entity() runs again and must again suppress
    that fresh first publish, exactly like the original boot."""
    hass.states.async_set("binary_sensor.dnd_test", "off")
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.runtime_data.context.scenario_registry.scenarios["sera"].enabled is True

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.runtime_data.context.scenario_registry.scenarios["sera"].enabled is True


def test_pending_first_publish_is_cleared_after_the_first_event() -> None:
    """The suppression only ever swallows one event per registration - a second state change
    for the same scenario is treated as a real toggle, not silently ignored forever."""
    registry = MagicMock()
    registry._pending_first_publish = {"sera"}
    scenario = MagicMock()
    scenario.name = "sera"
    scenario.enabled = True
    registry.scenarios = {"sera": scenario}

    new_state = MagicMock()
    new_state.state = STATE_OFF
    first = ScenarioRegistry.handle_entity_state_change(registry, "binary_sensor.supernotify_scenario_sera", new_state)
    assert first is False
    assert scenario.enabled is True
    assert "sera" not in registry._pending_first_publish

    second = ScenarioRegistry.handle_entity_state_change(registry, "binary_sensor.supernotify_scenario_sera", new_state)
    assert second is True
    assert scenario.enabled is False


def test_register_entity_marks_pending_first_publish() -> None:
    registry = MagicMock()
    registry._entities = {}
    registry._pending_first_publish = set()
    entity = MagicMock()
    ScenarioRegistry.register_entity(registry, "sera", entity)
    assert "sera" in registry._pending_first_publish
    assert registry._entities["sera"] is entity


def test_unregister_entity_clears_pending_first_publish() -> None:
    registry = MagicMock()
    registry._entities = {"sera": MagicMock()}
    registry._pending_first_publish = {"sera"}
    ScenarioRegistry.unregister_entity(registry, "sera")
    assert "sera" not in registry._pending_first_publish
    assert "sera" not in registry._entities


# --- Bug #3: manual re-enable self-cancelling in the same tick ------------------------------


async def test_manual_re_enable_holds_until_the_next_real_refresh(hass: HomeAssistant) -> None:
    """Re-enabling a disabled scenario from Developer Tools must not be immediately undone by
    the entity re-evaluating its (still false) conditions and writing that back in the same
    tick."""
    hass.states.async_set("binary_sensor.dnd_test", "off")
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    scenario = entry.runtime_data.context.scenario_registry.scenarios["sera"]
    assert scenario.enabled is True  # bug #2 regression already covers the boot state

    # disable manually
    hass.states.async_set("binary_sensor.supernotify_scenario_sera", STATE_OFF)
    await hass.async_block_till_done()
    assert scenario.enabled is False

    # re-enable manually - conditions are still false (binary_sensor.dnd_test is still off)
    hass.states.async_set("binary_sensor.supernotify_scenario_sera", STATE_ON)
    await hass.async_block_till_done()
    assert scenario.enabled is True
    # and the manually-set state itself holds - it wasn't overwritten in the same tick
    state = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert state is not None
    assert state.state == STATE_ON


def test_handle_entity_state_change_does_not_write_ha_state() -> None:
    """Unit-level guard for the fix itself: unlike an earlier version of this method, it must
    never call entity.async_write_ha_state() - that write is what caused the self-cancelling
    loop (see scenario.py's handle_entity_state_change docstring/comments)."""
    registry = MagicMock()
    entity = MagicMock()
    registry._entities = {"sera": entity}
    registry._pending_first_publish = set()
    scenario = MagicMock()
    scenario.name = "sera"
    scenario.enabled = False
    registry.scenarios = {"sera": scenario}

    new_state = MagicMock()
    new_state.state = STATE_ON
    ScenarioRegistry.handle_entity_state_change(registry, "binary_sensor.supernotify_scenario_sera", new_state)
    assert scenario.enabled is True
    entity.async_write_ha_state.assert_not_called()


# --- Medium bug: occupancy recomputed once per scenario in a batch refresh -----------------


def test_batch_refresh_computes_occupancy_once_for_the_whole_batch() -> None:
    """determine_occupancy() must be called once for the whole refresh, not once per scenario
    in it - the regression the review flagged as a design smell that scales badly."""
    registry = MagicMock()
    registry.scenario_control = {}
    registry._people_registry.determine_occupancy.return_value = {}
    registry._batch_cvars = None
    registry._scenario_by_entity = {}
    scenarios = {}
    entities = {}
    for name in ("dnd", "night", "away"):
        scenario = MagicMock()
        scenario.name = name
        scenarios[name] = scenario
        entities[name] = MagicMock()
    registry.scenarios = scenarios
    registry._entities = entities

    ScenarioRegistry.async_refresh_scenario_states(registry)

    registry._people_registry.determine_occupancy.assert_called_once()
    for entity in entities.values():
        entity.async_write_ha_state.assert_called_once()


def test_batch_cvars_reset_to_none_after_refresh() -> None:
    """_batch_cvars must not leak past the refresh - a later on-demand scenario_is_on() call
    (e.g. a single entity being read outside of a batch) must compute its own occupancy."""
    registry = MagicMock()
    registry.scenario_control = {}
    registry._people_registry.determine_occupancy.return_value = {}
    registry._batch_cvars = None
    registry._scenario_by_entity = {}
    registry.scenarios = {}
    registry._entities = {}

    ScenarioRegistry.async_refresh_scenario_states(registry)

    assert registry._batch_cvars is None


def test_scenario_is_on_uses_the_shared_batch_cvars_when_set() -> None:
    """scenario_is_on() must thread self._batch_cvars through to _scenario_state instead of
    letting it compute its own occupancy - the whole point of the batch snapshot.

    Uses a real (if bare) ScenarioRegistry instance rather than a MagicMock `self`: scenario_is_on
    calls self._scenario_state() internally, and on a MagicMock that inner call would hit an
    auto-generated mock method instead of the real one under test."""
    registry = ScenarioRegistry.__new__(ScenarioRegistry)
    registry._scenario_cond_entities = {"s": {"input_boolean.dnd"}}
    sentinel_cvars = MagicMock()
    registry._batch_cvars = sentinel_cvars
    scenario = MagicMock()
    scenario.name = "s"
    scenario.conditions_config = [{"condition": "state"}]
    scenario.evaluate.return_value = True
    scenario.expose_state = True

    registry.scenario_is_on(scenario)

    scenario.evaluate.assert_called_once_with(sentinel_cvars)


# --- Minor: recipient binary_sensor device_class ---------------------------------------------


def test_recipient_binary_sensor_has_no_misleading_device_class() -> None:
    """CONNECTIVITY (a previous version of this class) means online/offline device
    reachability, not "enabled for delivery" - a disabled recipient must not show up as
    "Disconnected" in the dashboard.

    Checks the class's own __dict__ rather than getattr(): BinarySensorEntity (the base
    class) declares _attr_device_class as a property, so a plain getattr() would find that
    inherited property object instead of telling "not set here" from "set to None"."""
    from custom_components.supernotify.binary_sensor import SupernotifyRecipientBinarySensor

    assert "_attr_device_class" not in SupernotifyRecipientBinarySensor.__dict__
