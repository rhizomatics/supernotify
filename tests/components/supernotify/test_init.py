"""Tests for SuperNotify config-entry setup/unload (Phase 1).

Convention: logic in __init__.py (async_setup_entry / async_unload_entry) is
tested in test_init.py. File path in the package:
tests/components/supernotify/test_init.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ENABLED
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.supernotify import ATTR_IMPORTED_FROM_YAML, DOMAIN
from custom_components.supernotify.const import (
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_TEMPLATE_PATH,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


_IMPORTED_ENTRY_DATA = {
    CONF_TEMPLATE_PATH: "/config/templates/supernotify",
    CONF_ARCHIVE: {CONF_ENABLED: False, CONF_ARCHIVE_DAYS: 3},
    ATTR_IMPORTED_FROM_YAML: True,
}


async def test_setup_and_unload_imported_entry(hass: HomeAssistant) -> None:
    """An entry imported from YAML loads (mirroring settings) and unloads cleanly.

    The legacy notify platform owns the service, so async_setup_entry must NOT
    forward/reload it — it should simply load the entry to LOADED state.
    """
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=_IMPORTED_ENTRY_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_triggers_reload(hass: HomeAssistant) -> None:
    """Updating the entry triggers the update listener (reload), staying LOADED."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=_IMPORTED_ENTRY_DATA)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(entry, options={"delivery": {"x": {}}})
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
