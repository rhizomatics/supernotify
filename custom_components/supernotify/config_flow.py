"""Config flow for the SuperNotify integration — Phase 1.

Phase 1 scope (see design/config_flow_design.md):
  * Register SuperNotify as a config-entry-based integration.
  * `async_step_user`  : manual setup, global settings only.
  * `async_step_import`: one-shot migration of an existing YAML configuration.

Out of scope for Phase 1 (handled by YAML until Phase 2/3 subentries land):
  * Delivery, scenario, recipient, camera, action-group management.

Design decisions for Phase 1:
  * Single config entry per HA instance (`unique_id == DOMAIN`).
  * Global settings are stored in `entry.data`; imported deliveries/scenarios and
    the other item collections are parked in `entry.options` untouched, so the
    existing runtime keeps working without behaviour changes.
  * The `notify.supernotify` action name is preserved (see __init__.py, which
    loads the legacy notify platform from the entry via discovery).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import ATTR_IMPORTED_FROM_YAML, DOMAIN, MEDIA_DIR, TEMPLATE_DIR
from .const import (
    ATTR_DUPE_POLICY_MT,
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    CONF_ACTION_GROUPS,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_HOUSEKEEPING,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SCENARIOS,
    CONF_SIZE,
    CONF_SNOOZE,
    CONF_SNOOZE_TIME,
    CONF_TEMPLATE_PATH,
    CONF_TRANSPORTS,
    CONF_TTL,
)

_LOGGER = logging.getLogger(__name__)

# Keys collected by the Phase 1 "global settings" form. Defaults mirror the
# top-level voluptuous schema (schema.py PLATFORM_SCHEMA.extend) so that moving
# from YAML to the UI does not change behaviour.
_DUPE_POLICIES = [ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE]


def _global_settings_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the global-settings form schema, pre-filled with `defaults`."""
    return vol.Schema({
        # NB: use cv.string (not cv.path) — cv.path is not JSON-serializable
        # by voluptuous_serialize for the config-flow frontend and raises
        # "Unable to convert schema" (HTTP 500) when rendering the form.
        vol.Optional(CONF_TEMPLATE_PATH, default=defaults.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR)): cv.string,
        vol.Optional(CONF_MEDIA_PATH, default=defaults.get(CONF_MEDIA_PATH, MEDIA_DIR)): cv.string,
        vol.Optional(
            CONF_MEDIA_URL_PREFIX,
            default=defaults.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media"),
        ): cv.string,
        vol.Optional(CONF_MOBILE_DISCOVERY, default=defaults.get(CONF_MOBILE_DISCOVERY, True)): cv.boolean,
        vol.Optional(
            CONF_RECIPIENTS_DISCOVERY,
            default=defaults.get(CONF_RECIPIENTS_DISCOVERY, True),
        ): cv.boolean,
        # Archive: only the two most common knobs in Phase 1.
        vol.Optional("archive_enabled", default=defaults.get("archive_enabled", False)): cv.boolean,
        vol.Optional("archive_days", default=defaults.get("archive_days", 3)): cv.positive_int,
        # Dupe check.
        vol.Optional("dupe_ttl", default=defaults.get("dupe_ttl", 120)): cv.positive_int,
        vol.Optional("dupe_size", default=defaults.get("dupe_size", 100)): cv.positive_int,
        vol.Optional("dupe_policy", default=defaults.get("dupe_policy", ATTR_DUPE_POLICY_MTSLP)): SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=p, label=p) for p in _DUPE_POLICIES],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="dupe_policy",
            )
        ),
        # Snooze + media retention.
        vol.Optional("snooze_seconds", default=defaults.get("snooze_seconds", 60 * 60)): cv.positive_int,
        vol.Optional("media_storage_days", default=defaults.get("media_storage_days", 7)): cv.positive_int,
    })


def _form_to_entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Map the flat form fields into the nested runtime config structure.

    The nesting matches the YAML top-level keys.
    """
    return {
        CONF_TEMPLATE_PATH: user_input[CONF_TEMPLATE_PATH],
        CONF_MEDIA_PATH: user_input[CONF_MEDIA_PATH],
        CONF_MEDIA_URL_PREFIX: user_input[CONF_MEDIA_URL_PREFIX],
        CONF_MOBILE_DISCOVERY: user_input[CONF_MOBILE_DISCOVERY],
        CONF_RECIPIENTS_DISCOVERY: user_input[CONF_RECIPIENTS_DISCOVERY],
        CONF_ARCHIVE: {
            CONF_ENABLED: user_input["archive_enabled"],
            CONF_ARCHIVE_DAYS: user_input["archive_days"],
        },
        CONF_DUPE_CHECK: {
            CONF_TTL: user_input["dupe_ttl"],
            CONF_SIZE: user_input["dupe_size"],
            CONF_DUPE_POLICY: user_input["dupe_policy"],
        },
        CONF_SNOOZE: {CONF_SNOOZE_TIME: user_input["snooze_seconds"]},
        CONF_HOUSEKEEPING: {CONF_MEDIA_STORAGE_DAYS: user_input["media_storage_days"]},
    }


def _entry_data_to_form(data: dict[str, Any]) -> dict[str, Any]:
    """Reverse of _form_to_entry_data: nested entry data back to flat form fields.

    Used so the reconfigure form is pre-filled with the current values. Falls
    back to the same defaults used by the YAML schema.
    """
    archive = data.get(CONF_ARCHIVE, {})
    dupe = data.get(CONF_DUPE_CHECK, {})
    snooze = data.get(CONF_SNOOZE, {})
    house = data.get(CONF_HOUSEKEEPING, {})
    return {
        CONF_TEMPLATE_PATH: data.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR),
        CONF_MEDIA_PATH: data.get(CONF_MEDIA_PATH, MEDIA_DIR),
        CONF_MEDIA_URL_PREFIX: data.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media"),
        CONF_MOBILE_DISCOVERY: data.get(CONF_MOBILE_DISCOVERY, True),
        CONF_RECIPIENTS_DISCOVERY: data.get(CONF_RECIPIENTS_DISCOVERY, True),
        "archive_enabled": archive.get(CONF_ENABLED, False),
        "archive_days": archive.get(CONF_ARCHIVE_DAYS, 3),
        "dupe_ttl": dupe.get(CONF_TTL, 120),
        "dupe_size": dupe.get(CONF_SIZE, 100),
        "dupe_policy": dupe.get(CONF_DUPE_POLICY, ATTR_DUPE_POLICY_MTSLP),
        "snooze_seconds": snooze.get(CONF_SNOOZE_TIME, 60 * 60),
        "media_storage_days": house.get(CONF_MEDIA_STORAGE_DAYS, 7),
    }


class SupernotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SuperNotify (Phase 1)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual setup from the UI — global settings only."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="SuperNotify",
                data=_form_to_entry_data(user_input),
                options={},
            )

        return self.async_show_form(step_id="user", data_schema=_global_settings_schema({}))

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """One-shot migration of an existing YAML configuration.

        `import_data` is the YAML config already validated by SUPERNOTIFY_SCHEMA,
        plus the ATTR_IMPORTED_FROM_YAML marker set by notify.async_get_service.
        Global keys go into `entry.data`; the item collections (deliveries,
        scenarios, recipients, cameras, links, action groups, transports) are
        preserved verbatim in `entry.options` so the runtime stays identical.

        The marker is carried into `entry.data` so async_setup_entry knows the
        legacy notify platform already owns the service and must NOT reload it
        (otherwise notify.supernotify would be registered twice).
        """
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        payload = dict(import_data)
        imported = payload.pop(ATTR_IMPORTED_FROM_YAML, False)
        global_data, item_options = _split_global_vs_items(payload)
        # Make storable: SUPERNOTIFY_SCHEMA may have coerced template strings into
        # Template objects that can't be JSON-serialized into the config entry.
        global_data = _jsonify(global_data)
        item_options = _jsonify(item_options)
        global_data[ATTR_IMPORTED_FROM_YAML] = imported
        _LOGGER.info("SUPERNOTIFY importing YAML configuration into a config entry")
        return self.async_create_entry(title="SuperNotify (imported)", data=global_data, options=item_options)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user change the global settings of an existing entry.

        Global settings are config-entry *data* (not optional), so the HA
        guidance is to use a reconfigure step rather than an OptionsFlow. On
        submit we update the existing entry in place and reload — we never
        create a second entry. The ATTR_IMPORTED_FROM_YAML marker is preserved.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(entry, data_updates=_form_to_entry_data(user_input))

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_global_settings_schema(_entry_data_to_form(entry.data)),
        )


# Keys that represent configurable *items* (managed by YAML in Phase 1, and by
# subentries from Phase 2/3). Everything else in the YAML is a global setting.
_ITEM_KEYS = (
    CONF_DELIVERY,
    CONF_SCENARIOS,
    CONF_RECIPIENTS,
    CONF_CAMERAS,
    CONF_LINKS,
    CONF_ACTION_GROUPS,
    CONF_TRANSPORTS,
)


def _split_global_vs_items(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a validated YAML config into (global settings, item collections)."""
    global_data = {k: v for k, v in config.items() if k not in _ITEM_KEYS}
    item_options = {k: v for k, v in config.items() if k in _ITEM_KEYS}
    return global_data, item_options


def _jsonify(obj: Any) -> Any:
    """Recursively make a config value JSON-serializable for config-entry storage.

    The YAML config arrives ALREADY validated by SUPERNOTIFY_SCHEMA, which coerces
    fields such as volume_template / message_template into `Template` objects that
    are not JSON-serializable. Storing them (e.g. when a subentry is added and HA
    saves the whole entry) raises "Type is not JSON serializable: Template".
    Templates become their source string; any other non-serializable value falls
    back to str(). The runtime re-validates the raw config when it loads it.
    """
    if isinstance(obj, dict):
        return {k: _jsonify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonify(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    template = getattr(obj, "template", None)  # homeassistant Template -> source
    return template if isinstance(template, str) else str(obj)
