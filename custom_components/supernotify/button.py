"""Button platform: reset every runtime override in one press.

The same as calling supernotify.reset_overrides with no `kind` - every scenario, recipient,
delivery and transport switched on or off at runtime is put back to its configured state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .hass_api import ha_device_info

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import SupernotifyConfigEntry
    from .engine import SupernotifyEngine


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the reset overrides button."""
    _ = hass
    async_add_entities([SupernotifyResetOverridesButton(entry.runtime_data, entry.entry_id)])


class SupernotifyResetOverridesButton(ButtonEntity):
    """Put everything switched on or off at runtime back to its configured state."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reset_overrides"
    _attr_unique_id = "reset_overrides"
    _attr_should_poll = False

    def __init__(self, engine: SupernotifyEngine, entry_id: str) -> None:
        self._engine = engine
        self._attr_device_info = ha_device_info(entry_id)

    async def async_press(self) -> None:
        self._engine.reset_overrides()
