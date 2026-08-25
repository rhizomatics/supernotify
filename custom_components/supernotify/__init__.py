"""The Supernotify integration"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .notify import SupernotifyAction

    type SupernotifyConfigEntry = ConfigEntry[SupernotifyAction]

DOMAIN = "supernotify"

PLATFORMS = [Platform.NOTIFY]
TEMPLATE_DIR: str = "supernotify/templates"
MEDIA_DIR: str = "supernotify/media"

_LOGGER = logging.getLogger(__name__)

NOTIFY_SERVICE_NAME = "supernotify"

# Marker stored in entry.data for entries created by mirroring an existing YAML
# config into the UI (see notify.async_get_service and config_flow.async_step_import).
# The legacy YAML notify platform keeps owning notify.supernotify for these entries -
# async_setup_entry must not also register it, which would duplicate the service.
ATTR_IMPORTED_FROM_YAML = "imported_from_yaml"


def _entry_full_config(entry: SupernotifyConfigEntry) -> ConfigType:
    """Fold a config entry's data/options into a full SUPERNOTIFY_SCHEMA config dict.

    entry.data holds the flat "user" step fields; entry.options holds the nested
    archive/dupe_check/housekeeping sections from the options flow, already shaped to match
    the schema.
    """
    from homeassistant.const import CONF_PLATFORM

    from .schema import SUPERNOTIFY_SCHEMA

    # SUPERNOTIFY_SCHEMA extends HA's generic notify PLATFORM_SCHEMA, which requires a
    # "platform" key - meaningless for a config-entry setup, but needed to satisfy validation.
    return SUPERNOTIFY_SCHEMA({CONF_PLATFORM: DOMAIN, **entry.data, **entry.options})


async def async_setup_entry(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> bool:
    from .notify import async_register_supplemental_services, build_supernotify_action

    if entry.data.get(ATTR_IMPORTED_FROM_YAML):
        # This entry only mirrors an existing YAML config into the UI - the legacy
        # YAML notify platform already provides notify.supernotify for it.
        _LOGGER.debug("SUPERNOTIFY entry imported from YAML; legacy notify platform owns the service")
        return True

    if hass.services.has_service("notify", NOTIFY_SERVICE_NAME):
        _LOGGER.warning(
            "SUPERNOTIFY notify.%s is already registered, probably from a legacy YAML "
            "'notify: - platform: supernotify' block. Not registering it again from this "
            "config entry - remove one of the two configurations",
            NOTIFY_SERVICE_NAME,
        )
        return True

    full_config = _entry_full_config(entry)
    service: SupernotifyAction = build_supernotify_action(hass, full_config)
    try:
        await service.initialize()
    except Exception as err:
        _LOGGER.exception("SUPERNOTIFY failed to initialize, will retry")
        raise ConfigEntryNotReady(f"SUPERNOTIFY failed to initialize: {err}") from err
    await service.async_setup(hass, NOTIFY_SERVICE_NAME, NOTIFY_SERVICE_NAME)
    await service.async_register_services()
    async_register_supplemental_services(hass, service, full_config)
    entry.runtime_data = service
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> bool:
    from .notify import async_unregister_supplemental_services

    # runtime_data is only set if async_setup_entry actually registered the service (it's
    # skipped when a legacy YAML platform got there first).
    service: SupernotifyAction | None = getattr(entry, "runtime_data", None)
    if service is not None:
        await service.async_unregister_services()
        async_unregister_supplemental_services(hass)
    return True
