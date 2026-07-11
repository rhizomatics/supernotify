"""The SuperNotify integration — Phase 1 __init__.py.

This REPLACES the current 9-line __init__.py. It keeps the existing module-level
constants (imported by the rest of the package) and adds the config-entry
lifecycle while leaving the legacy YAML notify platform fully working.

Phase 1 behaviour:
  * `async_setup_entry`  : when the entry was created via the UI (no YAML), load
    the legacy notify platform from the entry through discovery, so a user with
    no YAML still gets `notify.supernotify`.
  * When the entry was imported from YAML, the legacy `notify:` platform already
    provides the service, so we do NOT reload it (avoids a duplicate service).
    The entry just mirrors the settings for the UI.
  * `async_unload_entry` : tidy up.

The YAML->entry import itself is triggered from notify.async_get_service (see
notify.py), because the SuperNotify config lives under a
legacy `notify:` platform, not under a top-level `supernotify:` domain — so there
is no domain-level async_setup hook to import from.

NOTE (open point for jeyrb, design §4/§8): preserving the exact `notify.supernotify`
action while moving to a config entry is the delicate part. This implementation
takes the lowest-risk route (discovery-loaded legacy platform). A future phase
may switch to a NotifyEntity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import Platform
from homeassistant.helpers import discovery

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "supernotify"

PLATFORMS = [Platform.NOTIFY]
# Platforms set up via the config entry (the notify platform is legacy/discovery).
_ENTRY_PLATFORMS = [Platform.SENSOR]
TEMPLATE_DIR: str = "/config/templates/supernotify"
MEDIA_DIR: str = "supernotify/media"

# Marker stored in entry.data when the entry was created by importing YAML.
# Used to avoid double-loading the notify service (the legacy platform already
# provides it in that case).
ATTR_IMPORTED_FROM_YAML = "imported_from_yaml"


async def async_setup(_hass: HomeAssistant, _config: ConfigType) -> bool:
    """YAML setup hook.

    The notify platform loads itself via async_get_service; nothing extra is
    required here for Phase 1.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SuperNotify from a config entry.

    Phase 1: the entry owns no runtime_data — the notify service is provided by
    the legacy notify platform (either loaded from YAML, or loaded from this entry
    via discovery for UI-only setups). runtime_data will become relevant when the
    integration moves to a NotifyEntity in a later phase.
    """
    # Diagnostic sensor (delivery inventory) — additive, independent of the notify
    # service; set up for both imported and UI-only entries.
    await hass.config_entries.async_forward_entry_setups(entry, _ENTRY_PLATFORMS)

    if entry.data.get(ATTR_IMPORTED_FROM_YAML):
        # The legacy `notify:` platform already provides notify.supernotify from
        # YAML. The entry only mirrors settings for the UI; do not reload.
        _LOGGER.debug("SUPERNOTIFY entry imported from YAML; legacy notify platform owns the service")
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
        return True

    # UI-created entry (no YAML): load the legacy notify platform via discovery,
    # passing the merged config (as discovery_info) so async_get_service can build
    # the service. The 5th arg is hass_config (the full HA config); we pass {} as
    # this legacy notify platform does not read from it.
    merged: dict[str, Any] = {**entry.data, **entry.options}
    merged.pop(ATTR_IMPORTED_FROM_YAML, None)
    hass.async_create_task(discovery.async_load_platform(hass, Platform.NOTIFY, DOMAIN, merged, {}))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    No runtime_data to tear down in Phase 1; update listeners are removed
    automatically via the async_on_unload registration in async_setup_entry.
    """
    return await hass.config_entries.async_unload_platforms(entry, _ENTRY_PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
