"""Sensor platform: the notification/failure counters as real, restorable entities.

Forwarded to from async_setup_entry in __init__.py once the SupernotifyAction (entry.
runtime_data) is fully initialized. Replaces the two raw `hass.states.async_set()` writes
SupernotifyAction previously made directly for "sensor.supernotify_notifications" /
"sensor.supernotify_failures" - those had no entity_registry entry at all, so there is no
pre-existing unique_id/entity_id to preserve here beyond keeping the same entity_id string.

Being a real RestoreSensor also fixes a real bug: the old counters were plain ints on
SupernotifyAction (self.sent / self.failures) with no persistence, so they silently reset to 0
on every Home Assistant restart. async_added_to_hass() below restores the last known value (and
feeds it back into SupernotifyAction so in-memory and displayed counts stay consistent) before
either counter increments again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.const import EntityCategory

from . import DOMAIN
from .hass_api import ha_device_info

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceInfo
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose the sent/failure counters as restorable sensor entities."""
    _ = hass
    service = entry.runtime_data
    device_info = ha_device_info(entry.entry_id)

    notifications_entity = SupernotifyCounterSensor(
        unique_id="notifications",
        entity_id=f"sensor.{DOMAIN}_notifications",
        translation_key="notifications",
        device_info=device_info,
        restore_callback=service.restore_sent,
    )
    failures_entity = SupernotifyCounterSensor(
        unique_id="failures",
        entity_id=f"sensor.{DOMAIN}_failures",
        translation_key="failures",
        device_info=device_info,
        restore_callback=service.restore_failures,
    )
    # SupernotifyAction keeps these to push future increments straight to the entity
    # (set_value()); see notify.py async_send_message/expose_entities. Falls back to the old
    # raw hass_api.set_state() when unset - e.g. tests that build SupernotifyAction directly
    # without going through a config entry, so no platform is ever set up.
    service._notifications_entity = notifications_entity
    service._failures_entity = failures_entity
    async_add_entities([notifications_entity, failures_entity])


class SupernotifyCounterSensor(RestoreSensor):
    """A monotonically increasing counter, restored across restarts."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_value = 0
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str,
        entity_id: str,
        translation_key: str,
        device_info: DeviceInfo,
        restore_callback: Callable[[int], None],
    ) -> None:
        self._attr_unique_id = unique_id
        self.entity_id = entity_id
        self._attr_translation_key = translation_key
        self._attr_device_info = device_info
        self._restore_callback = restore_callback

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, (int, float)):
            restored = int(last_data.native_value)
            self._attr_native_value = restored
            self._restore_callback(restored)

    def set_value(self, value: int) -> None:
        """Called by SupernotifyAction whenever the underlying counter changes."""
        self._attr_native_value = value
        if self.hass is not None:
            self.async_write_ha_state()
