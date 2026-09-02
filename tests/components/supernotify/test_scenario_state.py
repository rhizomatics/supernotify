"""Tests for scenario state exposure (fix: scenarios were stuck at STATE_UNKNOWN).

Covers the classification logic of `SupernotifyAction._scenario_state`:
  * a scenario with no conditions (manual / apply_scenarios only) -> UNKNOWN
  * a scenario whose conditions reference no entity (priority-only / transient)
    -> UNKNOWN
  * a scenario whose conditions reference entities (stateful / hybrid)
    -> ON/OFF from a neutral evaluation

File path in the package: tests/components/supernotify/test_scenario_state.py
The method is called unbound with a mock `self` so the test needs no running HA;
the refresh wiring (timer + state-change tracking) is an integration concern.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN

from custom_components.supernotify.notify import SupernotifyAction


def _evaluate_state(conditions_config, cond_entities, evaluate_result: bool) -> str:
    """Call SupernotifyAction._scenario_state with a mock self/scenario."""
    me = MagicMock()
    me._scenario_cond_entities = {"s": set(cond_entities)}
    me.context.people_registry.determine_occupancy.return_value = {}

    scenario = MagicMock()
    scenario.name = "s"
    scenario.conditions_config = conditions_config
    scenario.evaluate.return_value = evaluate_result

    return SupernotifyAction._scenario_state(me, scenario)


def test_manual_scenario_without_conditions_is_unknown() -> None:
    """A scenario with no conditions (e.g. emergency, applied explicitly) has no
    evaluable state -> UNKNOWN."""
    assert _evaluate_state(None, set(), True) == STATE_UNKNOWN
    assert _evaluate_state([], set(), True) == STATE_UNKNOWN


def test_transient_scenario_without_entities_is_unknown() -> None:
    """A scenario whose conditions reference no entity depends only on the
    per-notification priority (critical_panic/high_priority/alexa_low_whisper)
    -> transient -> UNKNOWN, not a misleading OFF."""
    assert _evaluate_state([{"condition": "template"}], set(), True) == STATE_UNKNOWN
    assert _evaluate_state([{"condition": "template"}], set(), False) == STATE_UNKNOWN


def test_stateful_scenario_reflects_evaluation() -> None:
    """A scenario with entity-backed conditions exposes ON/OFF from the neutral
    evaluation (current occupancy, medium priority)."""
    ents = {"input_boolean.notifier_dnd"}
    assert _evaluate_state([{"condition": "state"}], ents, True) == STATE_ON
    assert _evaluate_state([{"condition": "state"}], ents, False) == STATE_OFF


def test_stateful_uses_neutral_condition_variables() -> None:
    """When no cvars are passed, the state is computed from a freshly built
    neutral ConditionVariables (occupancy queried, medium priority)."""
    me = MagicMock()
    me._scenario_cond_entities = {"s": {"alarm_control_panel.home_alarm"}}
    me.context.people_registry.determine_occupancy.return_value = {}

    scenario = MagicMock()
    scenario.name = "s"
    scenario.conditions_config = [{"condition": "state"}]
    scenario.evaluate.return_value = True

    assert SupernotifyAction._scenario_state(me, scenario) == STATE_ON
    # occupancy was queried to build the neutral evaluation context
    me.context.people_registry.determine_occupancy.assert_called_once()
    scenario.evaluate.assert_called_once()


def _action_with_scenarios(names_to_entities: dict[str, set[str]], expose: dict[str, bool] | None = None) -> MagicMock:
    """A mock SupernotifyAction wired with a scenario registry and the entity index."""
    expose = expose or {}
    me = MagicMock()
    me._scenario_cond_entities = dict(names_to_entities)
    me.scenario_state_config = {}
    scenarios = {}
    for name in names_to_entities:
        scenario = MagicMock()
        scenario.name = name
        scenario.conditions_config = [{"condition": "state"}]
        scenario.evaluate.return_value = True
        scenario.expose_state = expose.get(name, True)
        scenario.attributes.return_value = {}
        scenarios[name] = scenario
    me.context.scenario_registry.scenarios = scenarios
    me.context.people_registry.determine_occupancy.return_value = {}
    me._scenario_by_entity = SupernotifyAction._index_scenarios_by_entity(me)
    return me


def test_entity_index_maps_entities_to_dependent_scenarios() -> None:
    me = _action_with_scenarios({
        "dnd": {"input_boolean.dnd"},
        "night": {"input_boolean.dnd", "sun.sun"},
        "away": {"person.lorenzo"},
    })
    assert me._scenario_by_entity["input_boolean.dnd"] == {"dnd", "night"}
    assert me._scenario_by_entity["sun.sun"] == {"night"}
    assert me._scenario_by_entity["person.lorenzo"] == {"away"}


def test_entity_index_skips_scenarios_opted_out() -> None:
    """A scenario with expose_state: false is never woken by an entity change."""
    me = _action_with_scenarios({"dnd": {"input_boolean.dnd"}, "heavy": {"input_boolean.dnd"}}, expose={"heavy": False})
    assert me._scenario_by_entity["input_boolean.dnd"] == {"dnd"}


def _refreshed(me: MagicMock) -> set[str]:
    return {call.args[0].rsplit("_", 1)[-1] for call in me.context.hass_api.set_state.call_args_list}


def test_state_change_refreshes_only_dependent_scenarios() -> None:
    """The point of the entity index: one sensor changing must not re-evaluate every scenario,
    which is what makes the cost proportional to the change rather than to the config size."""
    me = _action_with_scenarios({
        "dnd": {"input_boolean.dnd"},
        "night": {"input_boolean.dnd", "sun.sun"},
        "away": {"person.lorenzo"},
    })
    me.scenario_state_enabled = True
    event = MagicMock()
    event.data = {"entity_id": "person.lorenzo"}
    SupernotifyAction.async_refresh_scenario_states(me, event)
    assert _refreshed(me) == {"away"}


def test_state_change_for_unrelated_entity_does_nothing() -> None:
    me = _action_with_scenarios({"dnd": {"input_boolean.dnd"}})
    me.scenario_state_enabled = True
    event = MagicMock()
    event.data = {"entity_id": "light.kitchen"}
    SupernotifyAction.async_refresh_scenario_states(me, event)
    me.context.hass_api.set_state.assert_not_called()


def test_periodic_sweep_refreshes_everything() -> None:
    """The timer has no entity, so it evaluates the whole registry - the safety net for time
    windows and templates whose dependencies could not be extracted."""
    me = _action_with_scenarios({"dnd": {"input_boolean.dnd"}, "away": {"person.lorenzo"}})
    me.scenario_state_enabled = True
    SupernotifyAction.async_refresh_scenario_states(me)
    assert _refreshed(me) == {"dnd", "away"}


def test_refresh_is_a_no_op_when_disabled() -> None:
    me = _action_with_scenarios({"dnd": {"input_boolean.dnd"}})
    me.scenario_state_enabled = False
    SupernotifyAction.async_refresh_scenario_states(me)
    me.context.hass_api.set_state.assert_not_called()


def test_scenario_opted_out_of_state_stays_unknown() -> None:
    me = MagicMock()
    me._scenario_cond_entities = {"s": {"input_boolean.dnd"}}
    scenario = MagicMock()
    scenario.name = "s"
    scenario.conditions_config = [{"condition": "state"}]
    scenario.evaluate.return_value = True
    scenario.expose_state = False
    assert SupernotifyAction._scenario_state(me, scenario) == STATE_UNKNOWN
