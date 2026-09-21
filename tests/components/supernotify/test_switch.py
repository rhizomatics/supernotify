"""Tests for the switches overriding a configured enabled flag (switch.py): the override is kept
across a restart or reload for as long as the configured value it overrides is unchanged."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_mock_service,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
)

from custom_components.supernotify import CONFIG_SCHEMA, DOMAIN, KEY_YAML_CONFIG
from custom_components.supernotify.repairs import DELIVERY_TRANSPORT_BINARY_SENSOR_DEPRECATED_ISSUE_ID
from custom_components.supernotify.switch import OverrideStoredData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.engine import SupernotifyEngine
    from custom_components.supernotify.switch import Overridable

# kind -> entity_id of its switch in the config built by _config()
SWITCHES: dict[str, str] = {
    "scenario": "switch.supernotify_scenario_sera",
    "recipient": "switch.supernotify_recipient_joe",
    "delivery": "switch.supernotify_delivery_testing",
    "transport": "switch.supernotify_transport_generic",
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
        "delivery": context.delivery_registry.deliveries["testing"],
        "transport": context.delivery_registry.transports["generic"],
    }
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


async def test_transport_config_change_drops_inheriting_delivery_override(hass: HomeAssistant) -> None:
    """A delivery without its own `enabled:` has its transport's configured value, so changing
    that in the configuration ends the delivery's override too."""
    await _setup(hass, _config())
    await _turn(hass, SWITCHES["delivery"], on=False)

    engine = await _reload(hass, _config({"transport": False}))
    assert _model(engine, "delivery").config_enabled is False
    assert _model(engine, "delivery").enabled is False
    # configured on again: the override from before the change is gone, so it's on
    engine = await _reload(hass, _config({"transport": True}))
    assert _model(engine, "delivery").enabled is True
    assert _state(hass, SWITCHES["delivery"]) == STATE_ON


async def test_transport_config_change_keeps_delivery_own_override(hass: HomeAssistant) -> None:
    """A delivery with its own `enabled:` keeps its override whatever its transport's is."""
    await _setup(hass, _config({"delivery": True}))
    await _turn(hass, SWITCHES["delivery"], on=False)

    engine = await _reload(hass, _config({"delivery": True, "transport": False}))

    assert _model(engine, "delivery").config_enabled is True
    assert _model(engine, "delivery").enabled is False


async def test_extra_restore_state_data_round_trip(hass: HomeAssistant, kind: str) -> None:
    engine = await _setup(hass, _config())
    await _turn(hass, SWITCHES[kind], on=False)

    switch = next(s for s in engine.override_switches.values() if s.entity_id == SWITCHES[kind])
    data = switch.extra_restore_state_data
    assert data == OverrideStoredData(enabled=False, config_enabled=True)
    assert OverrideStoredData.from_dict(data.as_dict()) == data


async def test_switches_are_registered_with_the_engine_until_unloaded(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    assert set(SWITCHES.values()) <= {s.entity_id for s in engine.override_switches.values()}
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


# --- Delivery and transport switches ----------------------------------------------------------


async def test_delivery_and_transport_switches_created(hass: HomeAssistant) -> None:
    config = _config()
    config["delivery"]["Chat Room"] = {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"}
    await _setup(hass, config)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    registry = er.async_get(hass)

    for entity_id, unique_id in (
        ("switch.supernotify_delivery_testing", "delivery_testing"),
        ("switch.supernotify_delivery_chat_room", "delivery_Chat Room"),
        ("switch.supernotify_transport_generic", "transport_generic"),
    ):
        assert _state(hass, entity_id) == STATE_ON
        reg_entry = registry.async_get(entity_id)
        assert reg_entry is not None
        assert reg_entry.unique_id == unique_id
        assert reg_entry.entity_category == EntityCategory.CONFIG
        assert reg_entry.config_entry_id == entry.entry_id
        assert reg_entry.device_id is not None

    state = hass.states.get("switch.supernotify_delivery_chat_room")
    assert state is not None
    assert state.name == "SuperNotify Delivery Chat Room Enabled"
    assert state.attributes["transport"] == "generic"
    state = hass.states.get("switch.supernotify_transport_generic")
    assert state is not None
    assert state.name == "SuperNotify Transport generic Enabled"


async def test_delivery_names_slugified_alike_get_distinct_switches(hass: HomeAssistant) -> None:
    """Home Assistant resolves the clash with a suffix - the second one added gets `_2`."""
    config = _config()
    config["delivery"]["Chat Room"] = {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"}
    config["delivery"]["chat_room"] = {"transport": "generic", "target": ["testy.testy"], "action": "notify.send_message"}
    await _setup(hass, config)
    registry = er.async_get(hass)

    entity_ids = {
        registry.async_get_entity_id("switch", DOMAIN, "delivery_Chat Room"),
        registry.async_get_entity_id("switch", DOMAIN, "delivery_chat_room"),
    }
    assert entity_ids == {"switch.supernotify_delivery_chat_room", "switch.supernotify_delivery_chat_room_2"}


async def test_unloaded_transport_has_no_switch(hass: HomeAssistant) -> None:
    """Only a transport that is loaded gets a switch: not one configured not to load, not one
    without what it needs to work, and not one with no delivery to use it."""
    hass.states.async_set("notify.mock_notify_target", "unknown")
    config = _config()
    config["transports"] = {"notify_entity": {"load": False}}
    engine = await _setup(hass, config)

    assert "notify_entity" not in engine.context.delivery_registry.transports
    assert hass.states.get("switch.supernotify_transport_notify_entity") is None
    # telegram has no config entry and no explicit delivery
    assert hass.states.get("switch.supernotify_transport_telegram") is None
    # persistent has no prerequisites to check, so is always available
    assert _state(hass, "switch.supernotify_transport_persistent") == STATE_ON


async def test_unloaded_transport_switch_is_kept_in_the_registry(hass: HomeAssistant) -> None:
    """A transport can be missing just while what it depends on is starting up, so the switch
    from an earlier run is left alone rather than removed."""
    registry = er.async_get(hass)
    registry.async_get_or_create("switch", DOMAIN, "transport_telegram", suggested_object_id="supernotify_transport_telegram")
    await _setup(hass, _config())

    assert registry.async_get_entity_id("switch", DOMAIN, "transport_telegram") is not None


async def test_disabled_but_usable_transport_has_switch_off(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config({"transport": False}))

    assert _state(hass, "switch.supernotify_transport_generic") == STATE_OFF
    # a delivery with no `enabled:` of its own follows the configured transport
    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_OFF
    assert engine.context.delivery_registry.deliveries["testing"].config_enabled is False


async def test_delivery_switch_toggles_delivery(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    delivery = engine.context.delivery_registry.deliveries["testing"]

    await _turn(hass, "switch.supernotify_delivery_testing", on=False)
    assert delivery.enabled is False
    assert "testing" in engine.context.delivery_registry.disabled_deliveries
    assert hass.states.get("switch.supernotify_delivery_testing").attributes["enabled"] is False  # type: ignore[union-attr]

    await _turn(hass, "switch.supernotify_delivery_testing", on=True)
    assert delivery.enabled is True
    assert "testing" in engine.context.delivery_registry.enabled_deliveries


async def test_transport_switch_off_suppresses_deliveries(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "notify", "chat_server")
    config = _config()
    config["delivery"]["testing"]["action"] = "notify.chat_server"
    engine = await _setup(hass, config)

    await _turn(hass, "switch.supernotify_transport_generic", on=False)
    # the flags are independent: the delivery itself is still enabled
    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_ON
    assert engine.context.delivery_registry.deliveries["testing"].enabled is True
    await hass.services.async_call("notify", DOMAIN, {"message": "transport off"}, blocking=True)
    assert len(calls) == 0

    await _turn(hass, "switch.supernotify_transport_generic", on=True)
    await hass.services.async_call("notify", DOMAIN, {"message": "transport on"}, blocking=True)
    assert len(calls) == 1


async def test_transport_toggle_refreshes_delivery_transport_enabled(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing")
    await _setup(hass, _config())

    def transport_enabled(entity_id: str) -> object:
        state = hass.states.get(entity_id)
        assert state is not None
        return state.attributes["transport_enabled"]

    assert transport_enabled("switch.supernotify_delivery_testing") is True
    await _turn(hass, "switch.supernotify_transport_generic", on=False)
    assert transport_enabled("switch.supernotify_delivery_testing") is False
    assert transport_enabled("binary_sensor.supernotify_delivery_testing") is False
    # the delivery's own flag is unchanged
    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_ON
    await _turn(hass, "switch.supernotify_transport_generic", on=True)
    assert transport_enabled("switch.supernotify_delivery_testing") is True


async def test_restored_transport_shows_on_its_deliveries(hass: HomeAssistant) -> None:
    mock_restore_cache_with_extra_data(
        hass, [(State(SWITCHES["transport"], STATE_OFF), {"enabled": False, "config_enabled": True})]
    )
    await _setup(hass, _config())

    state = hass.states.get("switch.supernotify_delivery_testing")
    assert state is not None
    assert state.attributes["transport_enabled"] is False


async def test_runtime_enabled_delivery_becomes_implicit(hass: HomeAssistant) -> None:
    config = _config({"delivery": False})
    config["delivery"]["testing"]["inclusion"] = ["default"]
    await _setup(hass, config)

    async def implicit() -> dict[str, Any]:
        response = await hass.services.async_call(
            DOMAIN, "enquire_implicit_deliveries", None, blocking=True, return_response=True
        )
        assert response is not None
        return dict(response)

    assert "generic" not in await implicit()
    await _turn(hass, "switch.supernotify_delivery_testing", on=True)
    assert (await implicit())["generic"] == ["testing"]


async def test_runtime_enabled_fallback_delivery_is_used(hass: HomeAssistant) -> None:
    calls = async_mock_service(hass, "notify", "chat_server")
    config = _config()
    config["delivery"] = {
        "backup": {
            "transport": "generic",
            "target": ["testy.testy"],
            "action": "notify.chat_server",
            "inclusion": ["fallback"],
            "enabled": False,
        }
    }
    config["scenarios"] = {}
    config["transports"] = {"persistent": {"load": False}}
    await _setup(hass, config)

    await hass.services.async_call("notify", DOMAIN, {"message": "no fallback"}, blocking=True)
    assert len(calls) == 0
    await _turn(hass, "switch.supernotify_delivery_backup", on=True)
    await hass.services.async_call("notify", DOMAIN, {"message": "fallback"}, blocking=True)
    assert len(calls) == 1


# --- Deprecated delivery and transport binary_sensors ----------------------------------------


def _preexisting_binary_sensors(hass: HomeAssistant, *unique_ids: str, disabled: bool = False) -> None:
    """Register binary_sensors as an install from before the switches already has them"""
    registry = er.async_get(hass)
    for unique_id in unique_ids:
        registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            unique_id,
            suggested_object_id=f"supernotify_{unique_id}",
            disabled_by=er.RegistryEntryDisabler.USER if disabled else None,
        )


async def test_mirror_only_with_preexisting_row(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing")
    await _setup(hass, _config())

    assert _state(hass, "binary_sensor.supernotify_delivery_testing") == STATE_ON
    assert hass.states.get("binary_sensor.supernotify_transport_generic") is None
    reg_entry = er.async_get(hass).async_get("binary_sensor.supernotify_delivery_testing")
    assert reg_entry is not None
    assert reg_entry.entity_category == EntityCategory.DIAGNOSTIC
    assert reg_entry.device_id is not None


async def test_mirror_follows_switch(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", "transport_generic")
    await _setup(hass, _config())

    await _turn(hass, "switch.supernotify_delivery_testing", on=False)
    assert _state(hass, "binary_sensor.supernotify_delivery_testing") == STATE_OFF
    await _turn(hass, "switch.supernotify_transport_generic", on=False)
    assert _state(hass, "binary_sensor.supernotify_transport_generic") == STATE_OFF
    await _turn(hass, "switch.supernotify_transport_generic", on=True)
    assert _state(hass, "binary_sensor.supernotify_transport_generic") == STATE_ON


async def test_writing_legacy_binary_sensor_no_longer_toggles(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", "transport_generic")
    engine = await _setup(hass, _config())

    hass.states.async_set("binary_sensor.supernotify_delivery_testing", STATE_OFF)
    hass.states.async_set("binary_sensor.supernotify_transport_generic", STATE_OFF)
    await hass.async_block_till_done()

    assert engine.context.delivery_registry.deliveries["testing"].enabled is True
    assert engine.context.delivery_registry.transports["generic"].enabled is True
    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_ON


async def test_mirror_not_created_for_unloaded_transport(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "transport_telegram")
    engine = await _setup(hass, _config())

    assert hass.states.get("binary_sensor.supernotify_transport_telegram") is None
    assert engine.context.delivery_registry.legacy_entities() == []


async def test_mirror_deprecation_repair_only_if_enabled(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", disabled=True)
    await _setup(hass, _config())
    assert ir.async_get(hass).async_get_issue(DOMAIN, DELIVERY_TRANSPORT_BINARY_SENSOR_DEPRECATED_ISSUE_ID) is None

    er.async_get(hass).async_update_entity("binary_sensor.supernotify_delivery_testing", disabled_by=None)
    await _reload(hass)
    issue = ir.async_get(hass).async_get_issue(DOMAIN, DELIVERY_TRANSPORT_BINARY_SENSOR_DEPRECATED_ISSUE_ID)
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.is_persistent is True


async def test_no_mirror_or_repair_when_all_rows_disabled(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", "transport_generic", disabled=True)
    engine = await _setup(hass, _config())

    assert engine.context.delivery_registry.legacy_entities() == []
    assert ir.async_get(hass).async_get_issue(DOMAIN, DELIVERY_TRANSPORT_BINARY_SENSOR_DEPRECATED_ISSUE_ID) is None


async def test_legacy_row_without_config_entry_is_adopted(hass: HomeAssistant) -> None:
    """Rows from before entities were owned by the config entry have none."""
    _preexisting_binary_sensors(hass, "transport_generic")
    await _setup(hass, _config())
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    reg_entry = er.async_get(hass).async_get("binary_sensor.supernotify_transport_generic")
    assert reg_entry is not None
    assert reg_entry.config_entry_id == entry.entry_id


async def test_refresh_entities_rewrites_switches_and_mirrors(hass: HomeAssistant) -> None:
    _preexisting_binary_sensors(hass, "delivery_testing", "recipient_joe")
    engine = await _setup(hass, _config())
    # changed behind the entities' backs, so nothing has published it yet
    engine.context.delivery_registry.deliveries["testing"].enabled = False
    engine.context.people_registry.people["person.joe"].enabled = False
    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_ON

    await hass.services.async_call(DOMAIN, "refresh_entities", None, blocking=True)

    assert _state(hass, "switch.supernotify_delivery_testing") == STATE_OFF
    assert _state(hass, "binary_sensor.supernotify_delivery_testing") == STATE_OFF
    assert _state(hass, "switch.supernotify_recipient_joe") == STATE_OFF
    assert _state(hass, "binary_sensor.supernotify_recipient_joe") == STATE_OFF


async def test_reset_overrides_of_transport_refreshes_delivery_transport_enabled(hass: HomeAssistant) -> None:
    await _setup(hass, _config())
    await _turn(hass, SWITCHES["transport"], on=False)
    state = hass.states.get(SWITCHES["delivery"])
    assert state is not None
    assert state.attributes["transport_enabled"] is False

    await hass.services.async_call(DOMAIN, "reset_overrides", {"kind": "transport"}, blocking=True)

    state = hass.states.get(SWITCHES["delivery"])
    assert state is not None
    assert state.attributes["transport_enabled"] is True
