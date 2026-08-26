"""The Supernotify integration"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import CONF_NAME, SERVICE_RELOAD
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.reload import async_integration_yaml_config
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.loader import async_get_integration
from homeassistant.util import slugify

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

    from .notify import SupernotifyAction

    type SupernotifyConfigEntry = ConfigEntry[SupernotifyAction]

DOMAIN = "supernotify"

TEMPLATE_DIR: str = "supernotify/templates"
MEDIA_DIR: str = "supernotify/media"

_LOGGER = logging.getLogger(__name__)

NOTIFY_SERVICE_NAME = "supernotify"

# Key under hass.data[DOMAIN] holding the validated top-level `supernotify:` YAML section
# (delivery/transports/scenarios/recipients/cameras/action_groups/links/snooze - the 8 keys not
# yet configurable via ConfigFlow). Populated by async_setup, read by _entry_full_config.
KEY_YAML_CONFIG = "yaml_config"

# Deferred import: schema.py imports MEDIA_DIR/TEMPLATE_DIR back from this module, so it can
# only be imported here once those (and DOMAIN) are already defined above.
from .schema import SUPERNOTIFY_YAML_SCHEMA  # noqa: E402, RUF100, I001

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN, default=dict): SUPERNOTIFY_YAML_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


async def async_reload_yaml_config_and_entries(hass: HomeAssistant) -> None:
    """Re-read the top-level `supernotify:` YAML section from disk and reload every entry.

    Shared by the supernotify.reload service below and repairs.py's migration flow (which needs
    the freshly-migrated `supernotify.yaml` picked up immediately, without a restart).
    """
    new_config = await async_integration_yaml_config(hass, DOMAIN)
    hass.data.setdefault(DOMAIN, {})[KEY_YAML_CONFIG] = (new_config or {}).get(DOMAIN, {})
    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Stash the top-level `supernotify:` YAML section and wire up supernotify.reload.

    This is the only place that YAML section is ever read for a running instance - editing it
    and calling supernotify.reload (or the repairs.py migration flow) re-reads it and reloads
    the config entry, which is the sole, unconditional owner of notify.supernotify.
    """
    hass.data.setdefault(DOMAIN, {})[KEY_YAML_CONFIG] = config.get(DOMAIN, {})

    async def _async_reload(_call: ServiceCall) -> None:
        await async_reload_yaml_config_and_entries(hass)

    async_register_admin_service(hass, DOMAIN, SERVICE_RELOAD, _async_reload)

    if not hass.config_entries.async_entries(DOMAIN):
        from homeassistant.config_entries import SOURCE_IMPORT

        hass.async_create_task(hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data={}))

    return True


def _entry_full_config(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> ConfigType:
    """Fold a config entry's data/options and the stashed top-level YAML section into a full
    FULL_CONFIG_SCHEMA config dict.

    entry.data holds the flat "user" step fields; entry.options holds the nested
    archive/dupe_check/housekeeping sections from the options flow - both validated here via
    CONFIG_ENTRY_SCHEMA. hass.data[DOMAIN] holds the delivery/transports/scenarios/recipients/
    cameras/action_groups/links/snooze YAML section (see async_setup) - already validated once
    by CONFIG_SCHEMA when that YAML was first loaded, so it's merged in as-is rather than
    re-validated (a second pass would reject values schema validation already coerced, e.g.
    cv.template's Template objects - see CONFIG_ENTRY_SCHEMA's docstring in schema.py).
    """
    from .schema import CONFIG_ENTRY_SCHEMA

    yaml_config = hass.data.get(DOMAIN, {}).get(KEY_YAML_CONFIG, {})
    return {**CONFIG_ENTRY_SCHEMA({**entry.data, **entry.options}), **yaml_config}


async def async_setup_entry(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> bool:
    from .notification import set_version
    from .notify import async_register_supplemental_services, build_supernotify_action

    integration = await async_get_integration(hass, DOMAIN)
    set_version(str(integration.version) if integration.version else "unknown")

    # Matches the slugify(conf_name or SERVICE_NOTIFY) logic the legacy notify platform loader
    # used to apply to a YAML `name:` field, so an existing custom notify.<name> action (e.g.
    # `name: SuperNotifier` -> notify.supernotifier) keeps working once this entry becomes the
    # sole owner of registering it - see repairs.py, which carries a migrated entry's name over.
    service_name = slugify(entry.data.get(CONF_NAME) or NOTIFY_SERVICE_NAME)

    if hass.services.has_service("notify", service_name):
        _LOGGER.warning(
            "SUPERNOTIFY notify.%s is already registered - not registering it again from this config entry",
            service_name,
        )
        return True

    full_config = _entry_full_config(hass, entry)
    service: SupernotifyAction = build_supernotify_action(hass, full_config)
    try:
        await service.initialize()
    except Exception as err:
        _LOGGER.exception("SUPERNOTIFY Failed to initialize, will retry")
        raise ConfigEntryNotReady(f"SUPERNOTIFY Failed to initialize: {err}") from err
    await service.async_setup(hass, service_name, service_name)
    await service.async_register_services()
    async_register_supplemental_services(hass, service, full_config)
    entry.runtime_data = service
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> None:
    """Reload the entry so archive/dupe_check/housekeeping options apply immediately."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> bool:
    from .notify import async_unregister_supplemental_services

    service: SupernotifyAction | None = getattr(entry, "runtime_data", None)
    if service is not None:
        await service.async_unregister_services()
        async_unregister_supplemental_services(hass)
    return True
