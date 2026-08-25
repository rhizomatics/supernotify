"""Config flow for the Supernotify integration.

Covers the "Immediate" phase of docs/roadmap/configflow_approach.md: a UI setup path that
reproduces examples/minimal.yaml (everything auto-discovered, no required fields), plus
options pages for the archive, dupe_check and housekeeping settings. Deliveries, transports,
scenarios, recipients and cameras stay YAML-only for now (see the roadmap doc's Third phase).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from . import ATTR_IMPORTED_FROM_YAML, DOMAIN, MEDIA_DIR, TEMPLATE_DIR
from .const import (
    ATTR_DUPE_POLICY_MT,
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_EVENT_NAME,
    CONF_ARCHIVE_EVENT_SELECTION,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_ARCHIVE_PURGE_INTERVAL,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SIZE,
    CONF_TEMPLATE_PATH,
    CONF_TTL,
)

_DUPE_POLICIES = [ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE]


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    # cv.string, not cv.path: cv.path fails voluptuous-serialize schema conversion used by
    # the config flow frontend ("Unable to convert schema" / HTTP 500).
    defaults = defaults or {}
    return vol.Schema({
        vol.Optional(CONF_TEMPLATE_PATH, default=defaults.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR)): cv.string,
        vol.Optional(CONF_MEDIA_PATH, default=defaults.get(CONF_MEDIA_PATH, MEDIA_DIR)): cv.string,
        vol.Optional(CONF_MEDIA_URL_PREFIX, default=defaults.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media")): cv.string,
        vol.Optional(CONF_MOBILE_DISCOVERY, default=defaults.get(CONF_MOBILE_DISCOVERY, True)): cv.boolean,
        vol.Optional(CONF_RECIPIENTS_DISCOVERY, default=defaults.get(CONF_RECIPIENTS_DISCOVERY, True)): cv.boolean,
        vol.Optional(CONF_ARCHIVE_PATH, default=defaults.get(CONF_ARCHIVE_PATH, "")): cv.string,
    })


class SupernotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Supernotify config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Supernotify", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_user_schema())

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user change the global settings of an existing entry.

        These fields are config-entry *data* (set at initial setup), not options, so HA's
        guidance is a reconfigure step rather than the options flow - which instead covers
        archive/dupe_check/housekeeping, genuine runtime preferences.
        """
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=_user_schema(dict(entry.data)))

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """One-shot mirror of an existing YAML configuration into a config entry.

        `import_data` is the YAML config already validated by SUPERNOTIFY_SCHEMA. The legacy
        YAML notify platform keeps owning notify.supernotify (see notify.async_get_service) -
        this entry only mirrors the global settings into the UI, so YAML-only users get an
        Integrations-page presence. async_setup_entry sees ATTR_IMPORTED_FROM_YAML and skips
        registering a second notify.supernotify service.

        Editing an imported entry's settings here does not change the running service, which
        is still governed by the YAML file - that's the actual config to edit until deliveries/
        transports/scenarios/recipients move off YAML in a later phase.

        Duplicate-entry protection is the same single_config_entry manifest flag used by the
        user step (it covers SOURCE_IMPORT too), so no unique_id bookkeeping is needed here.
        """
        archive: dict[str, Any] = dict(import_data.get(CONF_ARCHIVE) or {})
        archive_path = archive.pop(CONF_ARCHIVE_PATH, None)

        data: dict[str, Any] = {
            CONF_TEMPLATE_PATH: import_data.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR),
            CONF_MEDIA_PATH: import_data.get(CONF_MEDIA_PATH, MEDIA_DIR),
            CONF_MEDIA_URL_PREFIX: import_data.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media"),
            CONF_MOBILE_DISCOVERY: import_data.get(CONF_MOBILE_DISCOVERY, True),
            CONF_RECIPIENTS_DISCOVERY: import_data.get(CONF_RECIPIENTS_DISCOVERY, True),
            CONF_ARCHIVE_PATH: archive_path or "",
            ATTR_IMPORTED_FROM_YAML: True,
        }
        options: dict[str, Any] = {}
        if archive:
            options[CONF_ARCHIVE] = archive
        if import_data.get(CONF_DUPE_CHECK):
            options[CONF_DUPE_CHECK] = import_data[CONF_DUPE_CHECK]
        if import_data.get(CONF_HOUSEKEEPING):
            options[CONF_HOUSEKEEPING] = import_data[CONF_HOUSEKEEPING]

        return self.async_create_entry(title="Supernotify (imported)", data=data, options=options)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> SupernotifyOptionsFlow:
        return SupernotifyOptionsFlow()


class SupernotifyOptionsFlow(OptionsFlow):
    """Options pages for archive, dupe_check and housekeeping settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["archive", "dupe_check", "housekeeping"])

    async def async_step_archive(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current: dict[str, Any] = self.config_entry.options.get(CONF_ARCHIVE, {})
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_ARCHIVE: user_input})
        schema = vol.Schema({
            vol.Optional(CONF_ENABLED, default=current.get(CONF_ENABLED, False)): cv.boolean,
            vol.Optional(CONF_ARCHIVE_DAYS, default=current.get(CONF_ARCHIVE_DAYS, 3)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_MQTT_TOPIC, default=current.get(CONF_ARCHIVE_MQTT_TOPIC, "")): cv.string,
            vol.Optional(CONF_ARCHIVE_MQTT_QOS, default=current.get(CONF_ARCHIVE_MQTT_QOS, 0)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_MQTT_RETAIN, default=current.get(CONF_ARCHIVE_MQTT_RETAIN, True)): cv.boolean,
            vol.Optional(CONF_ARCHIVE_PURGE_INTERVAL, default=current.get(CONF_ARCHIVE_PURGE_INTERVAL, 60)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_EVENT_NAME, default=current.get(CONF_ARCHIVE_EVENT_NAME, "supernotification")): cv.string,
            vol.Optional(CONF_ARCHIVE_EVENT_SELECTION, default=current.get(CONF_ARCHIVE_EVENT_SELECTION, "NONE")): cv.string,
            vol.Optional(CONF_ARCHIVE_DIAGNOSTICS, default=current.get(CONF_ARCHIVE_DIAGNOSTICS, "ERROR")): cv.string,
        })
        return self.async_show_form(step_id="archive", data_schema=schema)

    async def async_step_dupe_check(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current: dict[str, Any] = self.config_entry.options.get(CONF_DUPE_CHECK, {})
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_DUPE_CHECK: user_input})
        schema = vol.Schema({
            vol.Optional(CONF_TTL, default=current.get(CONF_TTL, 120)): cv.positive_int,
            vol.Optional(CONF_SIZE, default=current.get(CONF_SIZE, 100)): cv.positive_int,
            vol.Optional(CONF_DUPE_POLICY, default=current.get(CONF_DUPE_POLICY, ATTR_DUPE_POLICY_MTSLP)): SelectSelector(
                SelectSelectorConfig(options=[SelectOptionDict(value=p, label=p) for p in _DUPE_POLICIES])
            ),
        })
        return self.async_show_form(step_id="dupe_check", data_schema=schema)

    async def async_step_housekeeping(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current: dict[str, Any] = self.config_entry.options.get(CONF_HOUSEKEEPING, {})
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_HOUSEKEEPING: user_input})
        schema = vol.Schema({
            vol.Optional(CONF_HOUSEKEEPING_TIME, default=current.get(CONF_HOUSEKEEPING_TIME, "00:00:01")): cv.string,
            vol.Optional(CONF_MEDIA_STORAGE_DAYS, default=current.get(CONF_MEDIA_STORAGE_DAYS, 7)): cv.positive_int,
        })
        return self.async_show_form(step_id="housekeeping", data_schema=schema)
