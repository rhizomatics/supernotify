"""Binary sensor platform: scenario and recipient state as real Home Assistant entities.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyAction (entry.
runtime_data) is fully initialized - scenario_registry.scenarios and people_registry.people are
already populated by then, mirroring notify.py's own async_setup_entry for recipient notify
entities.

These replace the raw hass_api.expose_entity()/hass.states.async_set() writes previously used
for scenario and recipient binary_sensors (see upstream issue #175, "Part B"): real
BinarySensorEntity objects grouped under a single SuperNotify device, instead of a bare
entity_registry entry with a hand-written state and no Entity object behind it.

entity_id and unique_id are chosen deliberately to line up with the pre-existing raw-write
scheme (binary_sensor.supernotify_scenario_<name> / _recipient_<name>, unique_id
"scenario_<name>" / "recipient_<name>" with no config-entry prefix) so that upgrading an
existing installation adopts the same entity_id and history instead of creating a duplicate -
see hass_api.expose_entity() for the scheme this continues. Delivery and transport
binary_sensors are unchanged in this PR - they keep their existing raw exposure pending a
separate, larger conversion to switch entities (entity_id migration + repair) discussed in the
same issue.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from . import DOMAIN
from .common import sanitize
from .hass_api import ha_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry
    from .people import PeopleRegistry, Recipient
    from .scenario import Scenario, ScenarioRegistry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose each scenario and recipient as its own binary_sensor entity."""
    _ = hass
    service = entry.runtime_data
    device_info = ha_device_info(entry.entry_id)

    entities: list[BinarySensorEntity] = [
        SupernotifyScenarioBinarySensor(scenario, service.context.scenario_registry, device_info)
        for scenario in service.context.scenario_registry.scenarios.values()
    ]
    entities.extend(
        SupernotifyRecipientBinarySensor(recipient, service.context.people_registry, device_info)
        for recipient in service.context.people_registry.people.values()
    )
    async_add_entities(entities)


class SupernotifyScenarioBinarySensor(BinarySensorEntity):
    """A scenario's evaluated condition state.

    See ScenarioRegistry._scenario_state()/scenario_is_on() for how ON/OFF/unknown is derived,
    and async_refresh_scenario_states() for what triggers a re-read of this entity's state.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Icon only (see icons.json) - _attr_name is set per-instance below from user config, so
    # translation_key never drives the displayed name, only the icon lookup.
    _attr_translation_key = "scenario"
    _attr_should_poll = False

    def __init__(self, scenario: Scenario, registry: ScenarioRegistry, device_info: DeviceInfo) -> None:
        self._scenario = scenario
        self._registry = registry
        self._attr_unique_id = f"scenario_{scenario.name}"
        self._attr_device_info = device_info
        self._attr_name = scenario.alias or scenario.name
        self.entity_id = f"binary_sensor.{DOMAIN}_scenario_{scenario.name}"

    @property
    def is_on(self) -> bool | None:
        return self._registry.scenario_is_on(self._scenario)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._scenario.attributes(include_condition=False))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._registry.register_entity(self._scenario.name, self)

    async def async_will_remove_from_hass(self) -> None:
        self._registry.unregister_entity(self._scenario.name)
        await super().async_will_remove_from_hass()


class SupernotifyRecipientBinarySensor(BinarySensorEntity):
    """Whether a recipient is currently enabled for delivery.

    Read-only here - toggling comes from the state_changed listener in notify.py
    (PeopleRegistry.handle_entity_state_change), not from this entity, matching how
    delivery/transport binary_sensors already work. Only delivery/transport are planned to
    become switch entities (see issue #175); recipients stay binary_sensor.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    # Icon only (see icons.json) - _attr_name is set per-instance below from user config, so
    # translation_key never drives the displayed name, only the icon lookup.
    _attr_translation_key = "recipient"
    _attr_should_poll = False

    def __init__(self, recipient: Recipient, registry: PeopleRegistry, device_info: DeviceInfo) -> None:
        self._recipient = recipient
        self._registry = registry
        self._attr_unique_id = f"recipient_{recipient.name}"
        self._attr_device_info = device_info
        self._attr_name = recipient.alias or recipient.name
        self.entity_id = f"binary_sensor.{DOMAIN}_recipient_{recipient.name}"

    @property
    def is_on(self) -> bool:
        return self._recipient.enabled

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._recipient.attributes())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._registry.register_entity(self._recipient.name, self)

    async def async_will_remove_from_hass(self) -> None:
        self._registry.unregister_entity(self._recipient.name)
        await super().async_will_remove_from_hass()
