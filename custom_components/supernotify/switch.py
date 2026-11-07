"""Switch platform: enable or disable each scenario, recipient, delivery and transport.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
runtime_data) is fully initialized.

A scenario's binary_sensor (binary_sensor.py) reports whether its *conditions* currently hold, so
it can't also be the control for enabling and disabling the scenario - writing its state used to do
both, and the two meanings fought each other. Recipient, delivery and transport binary_sensors had
no such conflict, but are treated the same way for consistency. These switches are the control,
and the binary_sensors are now read-only and kept only for backward compatibility.

A delivery and its transport each have their own switch, and their own flag: switching a
transport off suppresses all of its deliveries, without changing the delivery switches.

Each switch overrides the `enabled` value configured in YAML, and the override is kept across a
restart or reload (RestoreEntity) for as long as that configured value - its own `enabled`, or for
a delivery without one, its transport's - is unchanged. Editing it in YAML hands control back to
the configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import Context, callback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import slugify

from . import DOMAIN
from .common import sanitize
from .const import (
    ATTR_OVERRIDDEN,
    DELIVERY_UNRECORDED_ATTRIBUTES,
    OVERRIDE_KIND_DELIVERY,
    OVERRIDE_KIND_RECIPIENT,
    OVERRIDE_KIND_SCENARIO,
    OVERRIDE_KIND_TRANSPORT,
    SUBENTRY_TYPE_TRANSPORT,
    TRANSPORT_UNRECORDED_ATTRIBUTES,
    transport_display_name,
)
from .hass_api import ha_device_info, ha_transport_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry
    from .delivery import Delivery, DeliveryRegistry
    from .people import PeopleRegistry, Recipient
    from .scenario import Scenario, ScenarioRegistry
    from .transport import Transport

_LOGGER = logging.getLogger(__name__)

# Entities are pushed, never polled, and their actions only change local state
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a switch for each scenario, recipient, and loaded transport and delivery."""
    _ = hass
    context = entry.runtime_data.context
    switches = entry.runtime_data.override_switches
    device_info = ha_device_info(entry.entry_id)
    entities: list[SwitchEntity] = [
        SupernotifyScenarioSwitch(scenario, context.scenario_registry, device_info, switches)
        for scenario in context.scenario_registry.scenarios.values()
    ]
    # Only for what is loaded. The switch of a transport that isn't loaded this time, and of its
    # deliveries, is left in the entity registry rather than removed: a transport can be missing
    # just while what it depends on is still starting up
    delivery_registry = context.delivery_registry
    async_add_entities(entities)
    # each transport's on its own service device in its subentry, along with its deliveries' -
    # and each recipient's in its subentry, where it has one, with no device, so a recipient is
    # only listed once in the integration
    transport_subentries = {
        s.unique_id: s.subentry_id for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TYPE_TRANSPORT
    }
    for transport in delivery_registry.transports.values():
        # named by its alias, imported from YAML, else its name - and renamed in the UI as any device is
        transport_device = ha_transport_device_info(
            entry.entry_id, transport.name, transport.alias or transport_display_name(transport.name)
        )
        transport_entities: list[SwitchEntity] = [
            SupernotifyTransportSwitch(transport, delivery_registry, transport_device, switches)
        ]
        transport_entities.extend(
            SupernotifyDeliverySwitch(delivery, delivery_registry, transport_device, switches)
            for delivery in delivery_registry.deliveries.values()
            if delivery.transport.name == transport.name
        )
        async_add_entities(transport_entities, config_subentry_id=transport_subentries.get(transport.name))
    subentry_ids = context.people_registry.subentry_ids(entry.subentries)
    for recipient in context.people_registry.people.values():
        async_add_entities(
            [SupernotifyRecipientSwitch(recipient, context.people_registry, switches)],
            config_subentry_id=subentry_ids.get(recipient.key or ""),
        )


class Overridable(Protocol):
    """Anything with a configured enabled flag that a switch can override at runtime."""

    name: str
    enabled: bool
    config_enabled: bool


@dataclass(frozen=True)
class OverrideStoredData(ExtraStoredData):
    """What a switch keeps across a restart or reload: its state, and the configured value it
    was overriding, so that an override is dropped once the configuration changes."""

    enabled: bool
    config_enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {"enabled": self.enabled, "config_enabled": self.config_enabled}

    @classmethod
    def from_dict(cls, data: object) -> OverrideStoredData | None:
        """None unless data holds both values, as real booleans."""
        if isinstance(data, dict) and isinstance(data.get("enabled"), bool) and isinstance(data.get("config_enabled"), bool):
            return cls(enabled=data["enabled"], config_enabled=data["config_enabled"])
        return None


class SupernotifyOverridableSwitch(SwitchEntity, RestoreEntity):
    """A switch overriding the configured enabled flag of a scenario, recipient, delivery or
    transport, and keeping that override across a restart or reload while the configured value -
    its own `enabled`, or for a delivery without one, its transport's - is unchanged."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self,
        kind: str,
        target: Overridable,
        device_info: DeviceInfo | None,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        self._target = target
        self._switches = switches
        self._key = f"{kind}_{target.name}"
        self._attr_unique_id = self._key
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        return bool(self._target.enabled)

    def _with_overridden(self, attributes: dict[str, object]) -> dict[str, object]:
        """The switched item's own attributes, and whether the switch was changed at runtime - then
        it no longer matches the configured `enabled`, and reset_overrides would put it back."""
        return {**attributes, ATTR_OVERRIDDEN: bool(self._target.enabled) != bool(self._target.config_enabled)}

    @property
    def extra_restore_state_data(self) -> OverrideStoredData:
        # kept trivial: some Home Assistant versions don't guard this getter against errors
        return OverrideStoredData(enabled=bool(self._target.enabled), config_enabled=bool(self._target.config_enabled))

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._switches[self._key] = self
        last = await self.async_get_last_extra_data()
        stored = OverrideStoredData.from_dict(last.as_dict()) if last else None
        if stored is None:
            return
        if stored.config_enabled != self._target.config_enabled:
            _LOGGER.info("SUPERNOTIFY Configuration of %s changed, discarding its previous override", self._key)
            return
        if stored.enabled != self._target.enabled:
            _LOGGER.info("SUPERNOTIFY Restoring override of %s to %s", self._key, "on" if stored.enabled else "off")
            # no state write here - Home Assistant writes the first state once this returns
            self._apply_enabled(stored.enabled)

    async def async_will_remove_from_hass(self) -> None:
        self._switches.pop(self._key, None)
        await super().async_will_remove_from_hass()

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.async_set_enabled(False)

    @callback
    def async_set_enabled(self, enabled: bool, context: Context | None = None) -> bool:
        """Change the flag and publish it, returning whether anything changed.

        `context` is the action call that asked for the change, when that isn't this switch's own
        turn_on/turn_off, for which Home Assistant has already set it."""
        if enabled == self._target.enabled:
            return False
        if context is not None:
            self.async_set_context(context)
        self._apply_enabled(enabled)
        self.async_write_ha_state()
        return True

    def _apply_enabled(self, enabled: bool) -> None:
        self._target.enabled = enabled
        self._refresh_related()

    def _refresh_related(self) -> None:
        """Re-publish any other entity whose state follows this flag."""


class SupernotifyScenarioSwitch(SupernotifyOverridableSwitch):
    """Whether a scenario is enabled, and so able to apply to notifications."""

    _attr_translation_key = "scenario_enabled"

    def __init__(
        self,
        scenario: Scenario,
        registry: ScenarioRegistry,
        device_info: DeviceInfo,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        super().__init__(OVERRIDE_KIND_SCENARIO, scenario, device_info, switches)
        self._scenario = scenario
        self._registry = registry
        self._attr_translation_placeholders = {"scenario": scenario.alias or scenario.name}
        # Setting entity_id directly is not preferred Home Assistant practice - entities should
        # leave it to be derived from the device and entity name. It's done here so that a new
        # install gets the entity_id documented for scenarios (and used by the binary_sensor
        # this switch sits beside), which HA's own derivation would not produce. It has no effect
        # on an existing install: the entity registry entry found by unique_id always wins, so
        # nobody's entity_id, including one they have renamed, is changed by this.
        self.entity_id = f"switch.{DOMAIN}_scenario_{scenario.name}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return self._with_overridden(sanitize(self._scenario.attributes(include_condition=False)))

    def _refresh_related(self) -> None:
        # the condition state of a disabled scenario is always off, so that changes with this
        self._registry.async_refresh_entity(self._scenario.name, self._context)


class SupernotifyRecipientSwitch(SupernotifyOverridableSwitch):
    """Whether a recipient is enabled, and so able to be notified."""

    _attr_translation_key = "recipient_enabled"

    def __init__(
        self,
        recipient: Recipient,
        registry: PeopleRegistry,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        super().__init__(OVERRIDE_KIND_RECIPIENT, recipient, None, switches)
        self._attr_translation_placeholders = {"recipient": recipient.alias or recipient.name}
        self._recipient = recipient
        self._registry = registry
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch for why it's done anyway, and why it can't change the
        # entity_id of an existing install.
        self.entity_id = f"switch.{DOMAIN}_recipient_{recipient.name}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return self._with_overridden(sanitize(self._recipient.attributes()))

    def _refresh_related(self) -> None:
        # the deprecated binary_sensor mirrors enabled
        self._registry.async_refresh_entity(self._recipient.name)


class SupernotifyDeliverySwitch(SupernotifyOverridableSwitch):
    """Whether a delivery is enabled, and so able to be used for notifications."""

    _attr_translation_key = "delivery_enabled"
    _unrecorded_attributes = DELIVERY_UNRECORDED_ATTRIBUTES

    def __init__(
        self,
        delivery: Delivery,
        registry: DeliveryRegistry,
        device_info: DeviceInfo | None,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        super().__init__(OVERRIDE_KIND_DELIVERY, delivery, device_info, switches)
        self._delivery = delivery
        self._registry = registry
        self._attr_translation_placeholders = {"delivery": delivery.alias or delivery.name}
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch for why it's done anyway. Slugified, as a delivery name can be
        # any string.
        self.entity_id = f"switch.{DOMAIN}_delivery_{slugify(delivery.name)}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return self._with_overridden(sanitize(self._delivery.attributes()))

    def _refresh_related(self) -> None:
        # the deprecated binary_sensor mirrors enabled
        self._registry.async_refresh_entity(self._key)


class SupernotifyTransportSwitch(SupernotifyOverridableSwitch):
    """Whether a transport is enabled - when off, none of its deliveries are used."""

    _attr_translation_key = "transport_enabled"
    _unrecorded_attributes = TRANSPORT_UNRECORDED_ATTRIBUTES

    def __init__(
        self,
        transport: Transport,
        registry: DeliveryRegistry,
        device_info: DeviceInfo | None,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        super().__init__(OVERRIDE_KIND_TRANSPORT, transport, device_info, switches)
        self._transport = transport
        self._registry = registry
        # named after its device, the transport's own
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch and SupernotifyDeliverySwitch.
        self.entity_id = f"switch.{DOMAIN}_transport_{slugify(transport.name)}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return self._with_overridden(sanitize(self._transport.attributes()))

    def _refresh_related(self) -> None:
        # the deprecated binary_sensor mirrors enabled
        self._registry.async_refresh_entity(self._key)
        # and each of this transport's deliveries shows it, as transport_enabled
        for delivery in self._registry.deliveries.values():
            if delivery.transport is not self._transport:
                continue
            key = f"{OVERRIDE_KIND_DELIVERY}_{delivery.name}"
            switch = self._switches.get(key)
            if switch is not None:
                if self._context is not None:
                    switch.async_set_context(self._context)
                switch.async_write_ha_state()
            self._registry.async_refresh_entity(key)
