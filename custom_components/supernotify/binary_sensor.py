"""Binary sensor platform: scenario and recipient state as real Home Assistant entities.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
runtime_data) is fully initialized - scenario_registry.scenarios and people_registry.people are
already populated by then, mirroring notify.py's own async_setup_entry for recipient notify
entities.

These replace the raw hass_api.expose_entity()/hass.states.async_set() writes previously used
for scenario and recipient binary_sensors (see upstream issue #175, "Part B"): real
BinarySensorEntity objects grouped under a single SuperNotify device, instead of a bare
entity_registry entry with a hand-written state and no Entity object behind it.

The scenario and recipient binary_sensors are deprecated, kept only for backward compatibility,
only created for an existing install that already has them, and read-only: enabling and disabling a scenario or recipient is done by its switch entity
(switch.py). A one-off repair tells anyone with them enabled that they will be removed in a
future version (see repairs.py).

entity_id and unique_id are chosen deliberately to line up with the pre-existing raw-write
scheme (binary_sensor.supernotify_scenario_<name> / _recipient_<name>, unique_id
"scenario_<name>" / "recipient_<name>" with no config-entry prefix) so that upgrading an
existing installation adopts the same registry entry and history instead of creating a duplicate -
see hass_api.expose_entity() for the scheme this continues. Delivery and transport
binary_sensors are unchanged in this PR - they keep their existing raw exposure pending a
separate, larger conversion to switch entities (entity_id migration + repair) discussed in the
same issue.
"""

# CHANGELOG
# 2026-09-08: fix from the multi-agent review of the native scenario/recipient entities work:
# - SupernotifyRecipientBinarySensor: removed _attr_device_class = CONNECTIVITY, which was
#   semantically wrong (it means a device is online/offline, not "enabled for delivery") - a
#   disabled recipient showed as "Disconnected" in dashboards, which was misleading.

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

from . import DOMAIN
from .common import sanitize
from .hass_api import ha_device_info
from .repairs import async_create_binary_sensor_deprecated_issue

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
    """Keep the deprecated scenario and recipient binary_sensors, for an install that has them."""
    service = entry.runtime_data
    device_info = ha_device_info(entry.entry_id)

    candidates: list[BinarySensorEntity] = [
        SupernotifyScenarioBinarySensor(scenario, service.context.scenario_registry, device_info)
        for scenario in service.context.scenario_registry.scenarios.values()
    ]
    candidates.extend(
        SupernotifyRecipientBinarySensor(recipient, service.context.people_registry, device_info)
        for recipient in service.context.people_registry.people.values()
    )

    # These are deprecated, so only kept for an existing install that already has them, and never
    # published for anyone new - which includes a scenario or recipient added to an existing
    # install. Whether an entity exists is known from its registry entry, which is only created
    # by adding the entity.
    entity_registry = er.async_get(hass)
    entities: list[BinarySensorEntity] = []
    in_use = False
    for entity in candidates:
        entity_id = entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, entity.unique_id or "")
        registry_entry = entity_registry.async_get(entity_id) if entity_id else None
        if registry_entry is not None:
            entities.append(entity)
            # only worth a warning if somebody could still be relying on it
            in_use = in_use or registry_entry.disabled_by is None

    async_add_entities(entities)
    if in_use:
        async_create_binary_sensor_deprecated_issue(hass)


class SupernotifyScenarioBinarySensor(BinarySensorEntity):
    """A scenario's evaluated condition state. Deprecated, see the scenario switch.

    See ScenarioRegistry._scenario_state()/scenario_is_on() for how ON/OFF/unknown is derived,
    and async_refresh_scenario_states() for what triggers a re-read of this entity's state.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "scenario"
    _attr_should_poll = False

    def __init__(self, scenario: Scenario, registry: ScenarioRegistry, device_info: DeviceInfo) -> None:
        self._scenario = scenario
        self._registry = registry
        self._attr_unique_id = f"scenario_{scenario.name}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"scenario": scenario.alias or scenario.name}
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch for why it's done anyway, and why it can't change the
        # entity_id of an existing install.
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
    """Whether a recipient is currently enabled for delivery. Deprecated, see the recipient switch.

    Read-only: writing its state no longer enables or disables the recipient.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # No device_class: CONNECTIVITY (a previous version of this class) is semantically wrong
    # here - it means online/offline device reachability, not "enabled for delivery", and made
    # a disabled recipient show as "Disconnected" in the dashboard. Icon (see icons.json) and
    # translation_key below already carry the meaning without borrowing a misleading one.
    _attr_translation_key = "recipient"
    _attr_should_poll = False

    def __init__(self, recipient: Recipient, registry: PeopleRegistry, device_info: DeviceInfo) -> None:
        self._recipient = recipient
        self._registry = registry
        self._attr_unique_id = f"recipient_{recipient.name}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"recipient": recipient.alias or recipient.name}
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch for why it's done anyway, and why it can't change the
        # entity_id of an existing install.
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
