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
