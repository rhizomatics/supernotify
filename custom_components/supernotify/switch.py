"""Switch platform: enable or disable each scenario and recipient.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
runtime_data) is fully initialized.

A scenario's binary_sensor (binary_sensor.py) reports whether its *conditions* currently hold, so
it can't also be the control for enabling and disabling the scenario - writing its state used to do
both, and the two meanings fought each other. A recipient's binary_sensor had no such conflict, but
is treated the same way for consistency. These switches are the control, and the binary_sensors
are now read-only and kept only for backward compatibility.

TODO: deliveries and transports are still controlled by writing the state of their
binary_sensors (see issue #175), and are to move to switches in the same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
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
    """Add a switch for each scenario and recipient."""
    _ = hass
    context = entry.runtime_data.context
    device_info = ha_device_info(entry.entry_id)
    entities: list[SwitchEntity] = [
        SupernotifyScenarioSwitch(scenario, context.scenario_registry, device_info)
        for scenario in context.scenario_registry.scenarios.values()
    ]
    entities.extend(
        SupernotifyRecipientSwitch(recipient, context.people_registry, device_info)
        for recipient in context.people_registry.people.values()
    )
    async_add_entities(entities)


class SupernotifyScenarioSwitch(SwitchEntity):
    """Whether a scenario is enabled, and so able to apply to notifications."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "scenario_enabled"
    _attr_should_poll = False

    def __init__(self, scenario: Scenario, registry: ScenarioRegistry, device_info: DeviceInfo) -> None:
        self._scenario = scenario
        self._registry = registry
        self._attr_unique_id = f"scenario_{scenario.name}"
        self._attr_device_info = device_info
        self._attr_translation_placeholders = {"scenario": scenario.alias or scenario.name}
        # Setting entity_id directly is not preferred Home Assistant practice - entities should
        # leave it to be derived from the device and entity name. It's done here so that a new
        # install gets the entity_id documented for scenarios (and used by the binary_sensor
        # this switch sits beside), which HA's own derivation would not produce. It has no effect
        # on an existing install: the entity registry entry found by unique_id always wins, so
        # nobody's entity_id, including one they have renamed, is changed by this.
        self.entity_id = f"switch.{DOMAIN}_scenario_{scenario.name}"

    @property
    def is_on(self) -> bool:
        return self._scenario.enabled

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._scenario.attributes(include_condition=False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set_enabled(False)

    def _set_enabled(self, enabled: bool) -> None:
        self._scenario.enabled = enabled
        self.async_write_ha_state()
        # the condition state of a disabled scenario is always off, so that changes with this
        self._registry.async_refresh_entity(self._scenario.name)


class SupernotifyRecipientSwitch(SwitchEntity):
    """Whether a recipient is enabled, and so able to be notified."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "recipient_enabled"
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
        self.entity_id = f"switch.{DOMAIN}_recipient_{recipient.name}"

    @property
    def is_on(self) -> bool:
        return self._recipient.enabled

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return sanitize(self._recipient.attributes())

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set_enabled(False)

    def _set_enabled(self, enabled: bool) -> None:
        self._recipient.enabled = enabled
        self.async_write_ha_state()
        # the deprecated binary_sensor mirrors enabled
        self._registry.async_refresh_entity(self._recipient.name)
