"""Switch platform: enable or disable each scenario and recipient.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
runtime_data) is fully initialized.

A scenario's binary_sensor (binary_sensor.py) reports whether its *conditions* currently hold, so
it can't also be the control for enabling and disabling the scenario - writing its state used to do
both, and the two meanings fought each other. A recipient's binary_sensor had no such conflict, but
is treated the same way for consistency. These switches are the control, and the binary_sensors
are now read-only and kept only for backward compatibility.

Each switch overrides the `enabled` value configured in YAML, and the override is kept across a
restart or reload (RestoreEntity) for as long as that configured value is unchanged - editing
`enabled:` in YAML hands control back to the configuration.

TODO: deliveries and transports are still controlled by writing the state of their
binary_sensors (see issue #175), and are to move to switches in the same way.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from . import DOMAIN
from .common import sanitize
from .const import OVERRIDE_KIND_RECIPIENT, OVERRIDE_KIND_SCENARIO
from .hass_api import ha_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry
    from .people import PeopleRegistry, Recipient
    from .scenario import Scenario, ScenarioRegistry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a switch for each scenario and recipient."""
    _ = hass
    context = entry.runtime_data.context
    switches = entry.runtime_data.override_switches
    device_info = ha_device_info(entry.entry_id)
    entities: list[SwitchEntity] = [
        SupernotifyScenarioSwitch(scenario, context.scenario_registry, device_info, switches)
        for scenario in context.scenario_registry.scenarios.values()
    ]
    entities.extend(
        SupernotifyRecipientSwitch(recipient, context.people_registry, device_info, switches)
        for recipient in context.people_registry.people.values()
    )
    async_add_entities(entities)


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
    transport, and keeping that override across a restart or reload while the configured value
    is unchanged."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(
        self, kind: str, target: Overridable, device_info: DeviceInfo, switches: dict[str, SupernotifyOverridableSwitch]
    ) -> None:
        self._target = target
        self._switches = switches
        self._key = f"{kind}_{target.name}"
        self._attr_unique_id = self._key
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        return bool(self._target.enabled)

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
    def async_set_enabled(self, enabled: bool) -> bool:
        """Change the flag and publish it, returning whether anything changed."""
        if enabled == self._target.enabled:
            return False
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
        return sanitize(self._scenario.attributes(include_condition=False))

    def _refresh_related(self) -> None:
        # the condition state of a disabled scenario is always off, so that changes with this
        self._registry.async_refresh_entity(self._scenario.name)


class SupernotifyRecipientSwitch(SupernotifyOverridableSwitch):
    """Whether a recipient is enabled, and so able to be notified."""

    _attr_translation_key = "recipient_enabled"

    def __init__(
        self,
        recipient: Recipient,
        registry: PeopleRegistry,
        device_info: DeviceInfo,
        switches: dict[str, SupernotifyOverridableSwitch],
    ) -> None:
        super().__init__(OVERRIDE_KIND_RECIPIENT, recipient, device_info, switches)
        self._recipient = recipient
        self._registry = registry
        self._attr_translation_placeholders = {"recipient": recipient.alias or recipient.name}
        # Setting entity_id directly is not preferred Home Assistant practice - see
        # SupernotifyScenarioSwitch for why it's done anyway, and why it can't change the
        # entity_id of an existing install.
        self.entity_id = f"switch.{DOMAIN}_recipient_{recipient.name}"

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._recipient.attributes())

    def _refresh_related(self) -> None:
        # the deprecated binary_sensor mirrors enabled
        self._registry.async_refresh_entity(self._recipient.name)
