"""Scenarios and deliveries exposed as notify entities by `notify_entity`"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.notify import exposed_notify_entities
from custom_components.supernotify.schema import DELIVERY_SCHEMA, SCENARIO_SCHEMA

if TYPE_CHECKING:
    from custom_components.supernotify.engine import SupernotifyEngine

RAIN_SCENARIO = {
    "alias": "Its raining again",
    "notify_entity": "its_raining_again",
    "delivery": {"chat": {"data": {"priority": "low"}}},
}


async def _setup(
    hass: HomeAssistant,
    scenarios: dict[str, Any] | None = None,
    chat: dict[str, Any] | None = None,
    recipients: list[dict[str, Any]] | None = None,
) -> tuple[SupernotifyEngine, list[ServiceCall]]:
    calls: list[ServiceCall] = []

    async def _mock_notification(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("testing", "mock_notification", _mock_notification)
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "delivery": {
                    "chat": {
                        "transport": "generic",
                        "action": "testing.mock_notification",
                        "target_required": "never",
                        "inclusion": ["explicit"],
                        **(chat or {}),
                    }
                },
                "scenarios": scenarios or {},
                "recipients": recipients or [],
            }
        },
    )
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data, calls


async def _send(hass: HomeAssistant, entity_id: str, message: str) -> None:
    await hass.services.async_call(
        "notify", "send_message", {"entity_id": entity_id, "message": message, "title": "Weather"}, blocking=True
    )


async def test_scenario_notify_entity_applies_scenario(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    state = hass.states.get("notify.its_raining_again")
    assert state is not None
    assert state.attributes["friendly_name"] == "Its raining again"

    await _send(hass, "notify.its_raining_again", "Raining")

    assert engine.last_notification is not None
    assert engine.last_notification.applied_scenario_names == ["rain"]
    assert [(c.data["message"], c.data["title"]) for c in calls] == [("Raining", "Weather")]


async def test_delivery_notify_entity_selects_delivery(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, chat={"notify_entity": "family_chat"})

    await engine.async_send_message("not selected")
    assert calls == []

    await _send(hass, "notify.family_chat", "Dinner")

    assert [c.data["message"] for c in calls] == ["Dinner"]
    assert engine.last_notification is not None
    assert engine.last_notification.applied_scenario_names == []


async def test_no_notify_entity_unless_configured(hass: HomeAssistant) -> None:
    await _setup(hass, scenarios={"rain": {"delivery": {"chat": None}}})

    assert hass.states.async_entity_ids("notify") == []


async def test_existing_notify_entity_raises_repair(hass: HomeAssistant) -> None:
    hass.states.async_set("notify.its_raining_again", "unknown")

    _engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    assert er.async_get(hass).async_get("notify.its_raining_again") is None
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "notify_entity_scenario_rain")
    assert issue is not None
    assert issue.translation_key == "notify_entity_exists"
    assert issue.translation_placeholders == {"entity_id": "notify.its_raining_again", "kind": "scenario", "name": "rain"}
    assert calls == []


async def test_same_notify_entity_twice_raises_repair_for_second(hass: HomeAssistant) -> None:
    await _setup(hass, scenarios={"rain": RAIN_SCENARIO}, chat={"notify_entity": "its_raining_again"})

    assert len(hass.states.async_entity_ids("notify")) == 1
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "notify_entity_scenario_rain") is None
    assert issues.async_get_issue(DOMAIN, "notify_entity_delivery_chat") is not None


async def test_repair_cleared_and_entity_renamed_or_removed_with_config(hass: HomeAssistant) -> None:
    hass.states.async_set("notify.its_raining_again", "unknown")
    engine, _calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    registry = er.async_get(hass)
    scenario = engine.context.scenario_registry.scenarios["rain"]

    scenario.notify_entity = "rain"
    [entity] = exposed_notify_entities(hass, entry.entry_id, engine)
    assert entity.entity_id == "notify.rain"
    assert ir.async_get(hass).async_get_issue(DOMAIN, "notify_entity_scenario_rain") is None

    registry.async_get_or_create("notify", DOMAIN, entity.unique_id, config_entry=entry, suggested_object_id="rain")
    scenario.notify_entity = "wet"
    [entity] = exposed_notify_entities(hass, entry.entry_id, engine)
    assert entity.entity_id == "notify.wet"
    assert registry.async_get_entity_id("notify", DOMAIN, entity.unique_id) == "notify.wet"

    scenario.notify_entity = None
    assert exposed_notify_entities(hass, entry.entry_id, engine) == []
    assert registry.async_get_entity_id("notify", DOMAIN, entity.unique_id) is None


@pytest.mark.parametrize("schema", [SCENARIO_SCHEMA, DELIVERY_SCHEMA])
def test_notify_entity_must_be_a_slug(schema: vol.Schema) -> None:
    config = {"transport": "generic"} if schema is DELIVERY_SCHEMA else {}
    assert schema({**config, "notify_entity": "its_raining_again"})["notify_entity"] == "its_raining_again"
    with pytest.raises(vol.Invalid):
        schema({**config, "notify_entity": "notify.Its Raining"})


async def test_alert_notifies_scenario_by_name(hass: HomeAssistant) -> None:
    """The Alert integration only calls notify actions, so needs the one alongside the notify entity"""
    engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})
    hass.states.async_set("binary_sensor.rain", "off")
    assert await async_setup_component(
        hass,
        "alert",
        {
            "alert": {
                "rain": {
                    "name": "Its raining again",
                    "entity_id": "binary_sensor.rain",
                    "repeat": 30,
                    "notifiers": ["its_raining_again"],
                }
            }
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.rain", "on")
    await hass.async_block_till_done()

    assert [c.data["message"] for c in calls] == ["Its raining again"]
    assert engine.last_notification is not None
    assert engine.last_notification.applied_scenario_names == ["rain"]


async def test_scenario_notify_action_takes_title_data_and_target(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    await hass.services.async_call(
        "notify",
        "its_raining_again",
        {"message": "Raining", "title": "Weather", "target": "switch.kettle", "data": {"priority": "high"}},
        blocking=True,
    )

    notification = engine.last_notification
    assert notification is not None
    assert notification.applied_scenario_names == ["rain"]
    assert notification.priority == "high"
    assert notification._target is not None
    assert notification._target.entity_ids == ["switch.kettle"]
    assert [(c.data["message"], c.data["title"]) for c in calls] == [("Raining", "Weather")]


async def test_delivery_notify_action_selects_delivery(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass, chat={"notify_entity": "family_chat"})

    await hass.services.async_call("notify", "family_chat", {"message": "Dinner"}, blocking=True)

    assert [c.data["message"] for c in calls] == ["Dinner"]


async def test_recipient_notify_action_targets_recipient(hass: HomeAssistant) -> None:
    hass.states.async_set("person.bob", "home", {"friendly_name": "Bob"})
    engine, calls = await _setup(hass, chat={"inclusion": ["default"]}, recipients=[{"person": "person.bob"}])

    await hass.services.async_call("notify", "recipient_bob", {"message": "Dinner"}, blocking=True)

    assert engine.last_notification is not None
    assert engine.last_notification._target is not None
    assert engine.last_notification._target.person_ids == ["person.bob"]
    assert [c.data["message"] for c in calls] == ["Dinner"]


async def test_existing_notify_action_raises_repair(hass: HomeAssistant) -> None:
    other_calls: list[ServiceCall] = []

    async def _other(call: ServiceCall) -> None:
        other_calls.append(call)

    hass.services.async_register("notify", "its_raining_again", _other)

    _engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    assert hass.states.get("notify.its_raining_again") is None
    assert ir.async_get(hass).async_get_issue(DOMAIN, "notify_entity_scenario_rain") is not None
    await hass.services.async_call("notify", "its_raining_again", {"message": "Raining"}, blocking=True)
    assert len(other_calls) == 1
    assert calls == []


async def test_main_notify_action_name_is_reserved(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass, chat={"notify_entity": "supernotify"})

    assert hass.states.get("notify.supernotify") is None
    assert ir.async_get(hass).async_get_issue(DOMAIN, "notify_entity_delivery_chat") is not None
    # still the main action, with nothing selecting the delivery
    await hass.services.async_call("notify", "supernotify", {"message": "Dinner"}, blocking=True)
    assert calls == []


async def test_notify_actions_removed_on_unload(hass: HomeAssistant) -> None:
    await _setup(hass, scenarios={"rain": RAIN_SCENARIO})
    assert hass.services.has_service("notify", "its_raining_again")

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)

    assert not hass.services.has_service("notify", "its_raining_again")


async def test_scenario_notify_entity_reaches_area_target(hass: HomeAssistant) -> None:
    area = ar.async_get(hass).async_create("Kitchen")
    registry = er.async_get(hass)
    chime = registry.async_get_or_create("switch", "testing", "kitchen_chime", suggested_object_id="kitchen_chime")
    registry.async_update_entity(chime.entity_id, area_id=area.id)
    registry.async_get_or_create("switch", "testing", "hall_chime", suggested_object_id="hall_chime")
    engine, calls = await _setup(
        hass,
        scenarios={"rain": {"notify_entity": "its_raining_again", "delivery": {"chat": {"target": {"area_id": area.id}}}}},
        chat={"target_required": "always"},
    )

    await _send(hass, "notify.its_raining_again", "Raining")

    assert engine.last_notification is not None
    [envelope] = engine.last_notification.delivered_envelopes
    assert envelope.target.entity_ids == ["switch.kitchen_chime"]
    assert [(c.data["message"], c.data["target"]) for c in calls] == [("Raining", "switch.kitchen_chime")]


@pytest.mark.parametrize("delivery", ["chat", ["chat"], {"chat": None}])
async def test_scenario_delivery_styles_switch_on_delivery(
    hass: HomeAssistant, delivery: str | list[str] | dict[str, None]
) -> None:
    """A single delivery, a list and a mapping are all accepted from YAML, as documented"""
    engine, calls = await _setup(hass, scenarios={"wet": {"delivery": delivery}})

    await engine.async_send_message("not selected")
    assert calls == []

    notification = await engine.async_send_message("Raining", data={"apply_scenarios": "wet"})

    assert notification is not None
    assert list(notification.selected_deliveries) == ["chat"]
    assert [c.data["message"] for c in calls] == ["Raining"]


async def test_scenario_notify_entity_as_target_is_short_circuited(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    notification = await engine.async_send_message("Raining", target=["notify.its_raining_again", "switch.kettle"])

    assert notification is not None
    assert notification.applied_scenario_names == ["rain"]
    assert notification._target is not None
    assert notification._target.entity_ids == ["switch.kettle"]
    # once, and from this notification, not from a second one made by calling the notify entity
    assert [c.data["message"] for c in calls] == ["Raining"]
    assert engine.last_notification is notification


async def test_delivery_notify_entity_as_target_is_short_circuited(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, chat={"notify_entity": "family_chat"})

    notification = await engine.async_send_message("Dinner", target={"entity_id": ["notify.family_chat"]})

    assert notification is not None
    assert list(notification.delivery_overrides) == ["chat"]
    assert notification._target is None or notification._target.entity_ids == []
    assert [c.data["message"] for c in calls] == ["Dinner"]
    assert engine.last_notification is notification


async def test_notify_entity_as_target_adds_to_scenarios_and_deliveries_asked_for(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO, "other": {}}, chat={"notify_entity": "family_chat"})

    notification = await engine.async_send_message(
        "Raining",
        target=["notify.its_raining_again", "notify.family_chat"],
        data={"apply_scenarios": "other", "delivery": {"chat": {"data": {"priority": "high"}}}},
    )

    assert notification is not None
    assert notification.applied_scenario_names == ["other", "rain"]
    assert notification.delivery_overrides["chat"].data == {"priority": "high"}


async def test_unexposed_notify_entity_as_target_is_left_alone(hass: HomeAssistant) -> None:
    """One taken by something else, so with a repair, isn't Supernotify's to short circuit"""
    hass.states.async_set("notify.its_raining_again", "unknown")
    engine, _calls = await _setup(hass, scenarios={"rain": RAIN_SCENARIO})

    notification = await engine.async_send_message("Raining", target="notify.its_raining_again")

    assert notification is not None
    assert notification.applied_scenario_names == []
    assert notification._target is not None
    assert notification._target.entity_ids == ["notify.its_raining_again"]
