"""Tests for the native scenario/recipient entities and counter sensors.

Covers the scenario switch (which owns enabling and disabling a scenario), the now read-only
scenario binary_sensor and its one-off deprecation repair, recipient binary_sensor toggling,
restorable notification counters, config entry ownership of exposed entities, and two
regressions found by the multi-agent review of this work: determine_occupancy() recomputed once
per scenario in a batch refresh instead of once for the batch, and a misleading CONNECTIVITY
device class on the recipient binary_sensor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.engine import SupernotifyEngine
from custom_components.supernotify.repairs import SCENARIO_BINARY_SENSOR_DEPRECATED_ISSUE_ID
from custom_components.supernotify.scenario import ScenarioRegistry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _setup_supernotify(hass: HomeAssistant, config: dict) -> SupernotifyEngine:
    """Same helper as test_config_yaml.py: bootstrap supernotify from a top-level
    `supernotify:` YAML config and return the live service."""
    if hass.states.get("binary_sensor.dnd_test") is None:
        # a scenario condition on a missing entity fails validation and the scenario is dropped
        hass.states.async_set("binary_sensor.dnd_test", "off")
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


# --- Scenario: binary_sensor reports conditions, switch controls enabled --------------------


async def test_scenario_binary_sensor_reflects_false_condition_and_scenario_stays_enabled(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.dnd_test", "off")
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))
    assert engine.context.scenario_registry.scenarios["sera"].enabled is True
    state = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert state is not None
    assert state.state == STATE_OFF


async def test_scenario_binary_sensor_reflects_true_condition_and_scenario_stays_enabled(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.dnd_test", "on")
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))
    assert engine.context.scenario_registry.scenarios["sera"].enabled is True
    state = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert state is not None
    assert state.state == STATE_ON


async def test_scenario_survives_config_entry_reload(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.dnd_test", "off")
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.runtime_data.context.scenario_registry.scenarios["sera"].enabled is True
    assert hass.states.get("switch.supernotify_scenario_sera").state == STATE_ON  # type: ignore[union-attr]


async def test_scenario_switch_enables_and_disables_scenario(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.dnd_test", "on")
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))
    scenario = engine.context.scenario_registry.scenarios["sera"]
    switch = hass.states.get("switch.supernotify_scenario_sera")
    assert switch is not None
    assert switch.state == STATE_ON

    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.supernotify_scenario_sera"}, blocking=True)
    await hass.async_block_till_done()
    assert scenario.enabled is False
    assert hass.states.get("switch.supernotify_scenario_sera").state == STATE_OFF  # type: ignore[union-attr]
    # a disabled scenario's conditions can't apply, and the binary_sensor follows straight away
    assert hass.states.get("binary_sensor.supernotify_scenario_sera").state == STATE_OFF  # type: ignore[union-attr]

    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.supernotify_scenario_sera"}, blocking=True)
    await hass.async_block_till_done()
    assert scenario.enabled is True
    assert hass.states.get("switch.supernotify_scenario_sera").state == STATE_ON  # type: ignore[union-attr]
    assert hass.states.get("binary_sensor.supernotify_scenario_sera").state == STATE_ON  # type: ignore[union-attr]


async def test_writing_scenario_binary_sensor_state_no_longer_controls_scenario(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.dnd_test", "on")
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))
    scenario = engine.context.scenario_registry.scenarios["sera"]

    hass.states.async_set("binary_sensor.supernotify_scenario_sera", STATE_OFF)
    await hass.async_block_till_done()

    assert scenario.enabled is True
    assert hass.states.get("switch.supernotify_scenario_sera").state == STATE_ON  # type: ignore[union-attr]


async def test_scenario_entities_have_config_entry_device_and_names(hass: HomeAssistant) -> None:
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    registry = er.async_get(hass)

    for entity_id in ("switch.supernotify_scenario_sera", "binary_sensor.supernotify_scenario_sera"):
        reg_entry = registry.async_get(entity_id)
        assert reg_entry is not None
        assert reg_entry.config_entry_id == entry.entry_id
        assert reg_entry.device_id is not None
        assert reg_entry.unique_id == "scenario_sera"

    binary = hass.states.get("binary_sensor.supernotify_scenario_sera")
    assert binary is not None
    assert binary.name == "SuperNotify Evening mode Scenario"
    assert hass.states.get("switch.supernotify_scenario_sera").name == "SuperNotify Evening mode Scenario Enabled"  # type: ignore[union-attr]


async def test_scenario_binary_sensor_deprecation_repair_is_raised_once(hass: HomeAssistant) -> None:
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(DOMAIN, SCENARIO_BINARY_SENSOR_DEPRECATED_ISSUE_ID)
    assert issue is not None
    assert issue.is_fixable is False
    assert issue.is_persistent is True

    # once dismissed, it must not come back when the entry is set up again
    ir.async_ignore_issue(hass, DOMAIN, SCENARIO_BINARY_SENSOR_DEPRECATED_ISSUE_ID, True)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    issue = issues.async_get_issue(DOMAIN, SCENARIO_BINARY_SENSOR_DEPRECATED_ISSUE_ID)
    assert issue is not None
    assert issue.dismissed_version is not None


async def test_no_scenario_binary_sensor_repair_without_scenarios(hass: HomeAssistant) -> None:
    config = _stateful_scenario_config("on")
    config["scenarios"] = {}
    await _setup_supernotify(hass, config)
    assert ir.async_get(hass).async_get_issue(DOMAIN, SCENARIO_BINARY_SENSOR_DEPRECATED_ISSUE_ID) is None


# --- Recipient binary_sensor toggling ---------------------------------------------------------


async def test_recipient_binary_sensor_state_write_toggles_recipient(hass: HomeAssistant) -> None:
    hass.states.async_set("person.joe", "home")
    config = _stateful_scenario_config("on")
    config["recipients"] = [{"person": "person.joe"}]
    engine = await _setup_supernotify(hass, config)
    recipient = engine.context.people_registry.people["person.joe"]
    assert recipient.enabled is True
    entity_id = "binary_sensor.supernotify_recipient_joe"
    assert hass.states.get(entity_id).state == STATE_ON  # type: ignore[union-attr]

    hass.states.async_set(entity_id, STATE_OFF)
    await hass.async_block_till_done()
    assert recipient.enabled is False
    assert hass.states.get(entity_id).state == STATE_OFF  # type: ignore[union-attr]

    hass.states.async_set(entity_id, STATE_ON)
    await hass.async_block_till_done()
    assert recipient.enabled is True


# --- Counters --------------------------------------------------------------------------------


async def test_counters_are_the_only_home_of_the_counts(hass: HomeAssistant) -> None:
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))
    assert hass.states.get("sensor.supernotify_notifications").state == "0"  # type: ignore[union-attr]
    assert hass.states.get("sensor.supernotify_failures").state == "0"  # type: ignore[union-attr]

    engine.notifications_sensor.increment()
    engine.failures_sensor.increment()
    engine.failures_sensor.increment()
    await hass.async_block_till_done()

    assert engine.sent == 1
    assert engine.failures == 2
    assert hass.states.get("sensor.supernotify_notifications").state == "1"  # type: ignore[union-attr]
    assert hass.states.get("sensor.supernotify_failures").state == "2"  # type: ignore[union-attr]


async def test_counters_restore_their_last_value(hass: HomeAssistant) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (State("sensor.supernotify_notifications", "7"), {"native_value": 7, "native_unit_of_measurement": None}),
            (State("sensor.supernotify_failures", "3"), {"native_value": 3, "native_unit_of_measurement": None}),
        ],
    )
    engine = await _setup_supernotify(hass, _stateful_scenario_config("on"))

    assert engine.sent == 7
    assert engine.failures == 3
    assert hass.states.get("sensor.supernotify_notifications").state == "7"  # type: ignore[union-attr]

    engine.notifications_sensor.increment()
    assert engine.sent == 8


async def test_counter_sensors_are_on_the_supernotify_device(hass: HomeAssistant) -> None:
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    reg_entry = er.async_get(hass).async_get("sensor.supernotify_notifications")
    assert reg_entry is not None
    assert reg_entry.config_entry_id == entry.entry_id
    assert reg_entry.device_id is not None


# --- Raw exposed entities ----------------------------------------------------------------------


async def test_delivery_entities_belong_to_the_config_entry(hass: HomeAssistant) -> None:
    await _setup_supernotify(hass, _stateful_scenario_config("on"))
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    reg_entry = er.async_get(hass).async_get("binary_sensor.supernotify_delivery_testing")
    assert reg_entry is not None
    assert reg_entry.config_entry_id == entry.entry_id


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
