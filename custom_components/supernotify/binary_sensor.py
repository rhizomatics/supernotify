"""Binary sensor platform: scenario and recipient state as real Home Assistant entities.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
runtime_data) is fully initialized - scenario_registry.scenarios and people_registry.people are
already populated by then, mirroring notify.py's own async_setup_entry for recipient notify
entities.

These replace the raw entity registry and hass.states.async_set() writes previously used
for these binary_sensors (see upstream issue #175, "Part B"): real
BinarySensorEntity objects grouped under a single SuperNotify device, instead of a bare
entity_registry entry with a hand-written state and no Entity object behind it.

Both are read-only: enabling and disabling a scenario or recipient is done by its switch entity
(switch.py). The scenario binary_sensor is the only place a scenario's state - whether its
conditions currently hold, as opposed to whether it is enabled - is exposed, so is kept for
everyone, for any scenario that has conditions to evaluate. The recipient binary_sensor only mirrors the switch, so is deprecated, and only kept
for an existing install that already has it, never created for a new one. A one-off repair tells
anyone with it enabled that it will be removed in a future version (see repairs.py).

The delivery and transport binary_sensors are deprecated in the same way: enabling and disabling
moved to their switches, so these only mirror whether each is enabled, are kept only for an
existing install that already has them, and only for a delivery or transport that is loaded. A
one-off repair tells anyone with one enabled that they will be removed in a future version.

entity_id and unique_id are chosen deliberately to line up with the raw state writes these
entities replaced (binary_sensor.supernotify_scenario_<name> / _recipient_<name>, unique_id
"scenario_<name>" / "recipient_<name>" / "delivery_<name>" / "transport_<name>" with no
config-entry prefix) so that upgrading an existing installation adopts the same registry entry
and history instead of creating a duplicate.
"""

# CHANGELOG
# 2026-09-08: fix from the multi-agent review of the native scenario/recipient entities work:
# - SupernotifyRecipientBinarySensor: removed _attr_device_class = CONNECTIVITY, which was
#   semantically wrong (it means a device is online/offline, not "enabled for delivery") - a
#   disabled recipient showed as "Disconnected" in dashboards, which was misleading.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

from . import DOMAIN
from .common import sanitize
from .const import (
    DELIVERY_UNRECORDED_ATTRIBUTES,
    OVERRIDE_KIND_DELIVERY,
    OVERRIDE_KIND_TRANSPORT,
    TRANSPORT_UNRECORDED_ATTRIBUTES,
)
from .hass_api import ha_device_info
from .repairs import (
    async_create_delivery_transport_binary_sensor_deprecated_issue,
    async_create_recipient_binary_sensor_deprecated_issue,
)

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry
    from .delivery import Delivery, DeliveryRegistry
    from .people import PeopleRegistry, Recipient
    from .scenario import Scenario, ScenarioRegistry
    from .transport import Transport


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose the state of each scenario that has conditions to evaluate, and keep the deprecated
    recipient, delivery and transport binary_sensors for an install that has them."""
    service = entry.runtime_data
    device_info = ha_device_info(entry.entry_id)

    entity_registry = er.async_get(hass)
    entities: list[BinarySensorEntity] = []
    for scenario in service.context.scenario_registry.scenarios.values():
        if service.context.scenario_registry.scenario_has_state(scenario):
            entities.append(SupernotifyScenarioBinarySensor(scenario, service.context.scenario_registry, device_info))
        elif entity_id := entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, f"scenario_{scenario.name}"):
            # an install from before this had one, that could only ever have been unknown - remove
            # it rather than leave it as an entity that's no longer provided
            _LOGGER.info("SUPERNOTIFY Removing binary_sensor for scenario %s, it has no state to show", scenario.name)
            entity_registry.async_remove(entity_id)
            hass.states.async_remove(entity_id)

    # The recipient, delivery and transport binary_sensors are deprecated, so only kept for an
    # existing install that already has them, and never published for anyone new - which
    # includes a recipient, delivery or transport added to an existing install. Whether an entity
    # exists is known from its registry entry, which is only created by adding the entity.
    in_use = False
    for recipient in service.context.people_registry.people.values():
        registry_entry = _existing_row(entity_registry, f"recipient_{recipient.name}")
        if registry_entry is not None:
            entities.append(SupernotifyRecipientBinarySensor(recipient, service.context.people_registry, device_info))
            # only worth a warning if somebody could still be relying on it
            in_use = in_use or registry_entry.disabled_by is None

    delivery_registry = service.context.delivery_registry
    legacy_in_use = False
    legacy_sensors: list[SupernotifyLegacyBinarySensor] = [
        SupernotifyTransportBinarySensor(transport, delivery_registry, device_info)
        for transport in delivery_registry.transports.values()
    ]
    legacy_sensors.extend(
        SupernotifyDeliveryBinarySensor(delivery, delivery_registry, device_info)
        for delivery in delivery_registry.deliveries.values()
    )
    for legacy_sensor in legacy_sensors:
        registry_entry = _existing_row(entity_registry, legacy_sensor.unique_id or "")
        if registry_entry is not None:
            entities.append(legacy_sensor)
            legacy_in_use = legacy_in_use or registry_entry.disabled_by is None

    async_add_entities(entities)
    if in_use:
        async_create_recipient_binary_sensor_deprecated_issue(hass)
    if legacy_in_use:
        async_create_delivery_transport_binary_sensor_deprecated_issue(hass)


def _existing_row(entity_registry: er.EntityRegistry, unique_id: str) -> er.RegistryEntry | None:
    """The registry entry of one of our binary_sensors, if an earlier version already created it."""
    entity_id = entity_registry.async_get_entity_id(Platform.BINARY_SENSOR, DOMAIN, unique_id)
    return entity_registry.async_get(entity_id) if entity_id else None


class SupernotifyScenarioBinarySensor(BinarySensorEntity):
    """A scenario's evaluated condition state - whether it currently applies, as opposed to
    whether it is enabled, which is the scenario switch. Only created for a scenario that has
    conditions to evaluate (see ScenarioRegistry.scenario_has_state()).

    Read-only: writing its state does not enable or disable the scenario.

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


class SupernotifyLegacyBinarySensor(BinarySensorEntity):
    """Whether a delivery or transport is currently enabled. Deprecated, see its switch.

    Read-only: writing its state no longer enables or disables anything. No entity_id is set,
    as none is needed: an existing registry entry, found by unique_id, always provides it.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, kind: str, model: Delivery | Transport, registry: DeliveryRegistry, device_info: DeviceInfo) -> None:
        self._model = model
        self._registry = registry
        self._key = f"{kind}_{model.name}"
        self._attr_unique_id = self._key
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {kind: model.alias or model.name}

    @property
    def is_on(self) -> bool:
        return bool(self._model.enabled)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._model.attributes())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._registry.register_entity(self._key, self)

    async def async_will_remove_from_hass(self) -> None:
        self._registry.unregister_entity(self._key)
        await super().async_will_remove_from_hass()


class SupernotifyDeliveryBinarySensor(SupernotifyLegacyBinarySensor):
    """Whether a delivery is currently enabled. Deprecated, see the delivery switch."""

    _attr_translation_key = "delivery"
    _unrecorded_attributes = DELIVERY_UNRECORDED_ATTRIBUTES

    def __init__(self, delivery: Delivery, registry: DeliveryRegistry, device_info: DeviceInfo) -> None:
        super().__init__(OVERRIDE_KIND_DELIVERY, delivery, registry, device_info)


class SupernotifyTransportBinarySensor(SupernotifyLegacyBinarySensor):
    """Whether a transport is currently enabled. Deprecated, see the transport switch."""

    _attr_translation_key = "transport"
    _unrecorded_attributes = TRANSPORT_UNRECORDED_ATTRIBUTES

    def __init__(self, transport: Transport, registry: DeliveryRegistry, device_info: DeviceInfo) -> None:
        super().__init__(OVERRIDE_KIND_TRANSPORT, transport, registry, device_info)
