"""Sensor platform: the notification/failure counters as real, restorable entities.

The two SupernotifyCounterSensor entities are created by SupernotifyEngine itself (so they exist,
and count, even before this platform loads, or without a config entry at all) and just handed to
Home Assistant here. They are the single home of the counts - the engine has no separate copy -
and being RestoreSensors, the counts survive a Home Assistant restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.const import EntityCategory

from . import DOMAIN
from .hass_api import ha_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the engine's sent/failure counters as restorable sensor entities."""
    _ = hass
    async_add_entities(entry.runtime_data.counter_sensors)


class SupernotifyCounterSensor(RestoreSensor):
    """A monotonically increasing counter, restored across restarts."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_value = 0
    _attr_should_poll = False

    def __init__(self, unique_id: str, translation_key: str) -> None:
        self._attr_unique_id = unique_id
        self._attr_translation_key = translation_key
        # Kept as the entity_id the counters have always had, rather than the one HA would derive
        # from the device and entity name - see SupernotifyScenarioSwitch for why this is
        # tolerated
        self.entity_id = f"sensor.{DOMAIN}_{unique_id}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """The single SuperNotify device - the platform, and so the config entry, is only known
        once the entity has been handed to Home Assistant"""
        if self.platform is None or self.platform.config_entry is None:
            return None
        return ha_device_info(self.platform.config_entry.entry_id)

    @property
    def count(self) -> int:
        return int(self._attr_native_value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, (int, float)):
            self._attr_native_value = int(last_data.native_value)
            self.async_write_ha_state()

    def increment(self) -> None:
        self._attr_native_value = self.count + 1
        self.refresh()

    def refresh(self) -> None:
        """Publish the current count, if the entity has been added to Home Assistant yet"""
        if self.hass is not None:
            self.async_write_ha_state()
