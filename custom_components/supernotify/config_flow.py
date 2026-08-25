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
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

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
from .schema import OutcomeSelection

_DUPE_POLICIES = [ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE]


def _event_policy_str(value: Any) -> str:
    """Render an OutcomeSelection as the pipe-separated name string parse_event_policy
    expects (e.g. "ERROR|DUPE"), whatever form it currently happens to be in.

    A YAML-imported archive config already went through SUPERNOTIFY_SCHEMA, which turns
    event_selection/diagnostics into OutcomeSelection (IntFlag) instances - stored as a raw
    int once round-tripped through config-entry storage. Left unconverted, that raw int would
    show up as a bare number in this form instead of the "ERROR"-style text it's meant to be.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        try:
            return OutcomeSelection(value).name or "NONE"
        except ValueError:
            return "NONE"
    return str(value)


# NONE isn't a real, independently selectable outcome - it's the empty bitmask, and an
# always-false no-op check in archive.py (outcome_policy & OutcomeSelection.NONE is always
# 0). "No outcomes ticked" already means NONE, so it's excluded from the checkbox list.
_OUTCOME_OPTIONS = [flag.name for flag in OutcomeSelection if flag != OutcomeSelection.NONE and flag.name]


def _event_policy_to_list(value: Any) -> list[str]:
    """Turn a stored OutcomeSelection value into the list of names a multi-select needs."""
    policy_str = _event_policy_str(value)
    return [] if policy_str in ("", "NONE") else policy_str.split("|")


def _event_policy_from_list(values: list[str]) -> str:
    """Turn a submitted multi-select list back into the pipe-separated string
    SUPERNOTIFY_SCHEMA's parse_event_policy expects."""
    return "|".join(values) if values else "NONE"


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
        if CONF_ARCHIVE_EVENT_SELECTION in archive:
            archive[CONF_ARCHIVE_EVENT_SELECTION] = _event_policy_str(archive[CONF_ARCHIVE_EVENT_SELECTION])
        if CONF_ARCHIVE_DIAGNOSTICS in archive:
            archive[CONF_ARCHIVE_DIAGNOSTICS] = _event_policy_str(archive[CONF_ARCHIVE_DIAGNOSTICS])

        data: dict[str, Any] = {
            CONF_TEMPLATE_PATH: import_data.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR),
            CONF_MEDIA_PATH: import_data.get(CONF_MEDIA_PATH, MEDIA_DIR),
            CONF_MEDIA_URL_PREFIX: import_data.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media"),
            CONF_MOBILE_DISCOVERY: import_data.get(CONF_MOBILE_DISCOVERY, True),
            CONF_RECIPIENTS_DISCOVERY: import_data.get(CONF_RECIPIENTS_DISCOVERY, True),
            ATTR_IMPORTED_FROM_YAML: True,
        }
        housekeeping: dict[str, Any] = dict(import_data.get(CONF_HOUSEKEEPING) or {})
        housekeeping_time = housekeeping.get(CONF_HOUSEKEEPING_TIME)
        if housekeeping_time is not None and not isinstance(housekeeping_time, str):
            # cv.time on the YAML side already coerced this into a datetime.time
            housekeeping[CONF_HOUSEKEEPING_TIME] = housekeeping_time.isoformat()

        options: dict[str, Any] = {}
        if archive:
            options[CONF_ARCHIVE] = archive
        if import_data.get(CONF_DUPE_CHECK):
            options[CONF_DUPE_CHECK] = import_data[CONF_DUPE_CHECK]
        if housekeeping:
            options[CONF_HOUSEKEEPING] = housekeeping

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
            processed = dict(user_input)
            processed[CONF_ARCHIVE_EVENT_SELECTION] = _event_policy_from_list(user_input[CONF_ARCHIVE_EVENT_SELECTION])
            processed[CONF_ARCHIVE_DIAGNOSTICS] = _event_policy_from_list(user_input[CONF_ARCHIVE_DIAGNOSTICS])
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_ARCHIVE: processed})
        outcome_selector = SelectSelector(
            SelectSelectorConfig(options=_OUTCOME_OPTIONS, multiple=True, translation_key="outcome_selection")
        )
        schema = vol.Schema({
            vol.Optional(CONF_ENABLED, default=current.get(CONF_ENABLED, False)): cv.boolean,
            # cv.string, not cv.path: cv.path fails voluptuous-serialize schema conversion
            # used by the config flow frontend ("Unable to convert schema" / HTTP 500).
            vol.Optional(CONF_ARCHIVE_PATH, default=current.get(CONF_ARCHIVE_PATH, "")): cv.string,
            vol.Optional(CONF_ARCHIVE_DAYS, default=current.get(CONF_ARCHIVE_DAYS, 3)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_MQTT_TOPIC, default=current.get(CONF_ARCHIVE_MQTT_TOPIC, "")): cv.string,
            vol.Optional(CONF_ARCHIVE_MQTT_QOS, default=current.get(CONF_ARCHIVE_MQTT_QOS, 0)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_MQTT_RETAIN, default=current.get(CONF_ARCHIVE_MQTT_RETAIN, True)): cv.boolean,
            vol.Optional(CONF_ARCHIVE_PURGE_INTERVAL, default=current.get(CONF_ARCHIVE_PURGE_INTERVAL, 60)): cv.positive_int,
            vol.Optional(CONF_ARCHIVE_EVENT_NAME, default=current.get(CONF_ARCHIVE_EVENT_NAME, "supernotification")): cv.string,
            vol.Optional(
                CONF_ARCHIVE_EVENT_SELECTION,
                default=_event_policy_to_list(current.get(CONF_ARCHIVE_EVENT_SELECTION, "NONE")),
            ): outcome_selector,
            vol.Optional(
                CONF_ARCHIVE_DIAGNOSTICS, default=_event_policy_to_list(current.get(CONF_ARCHIVE_DIAGNOSTICS, "ERROR"))
            ): outcome_selector,
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
                SelectSelectorConfig(options=_DUPE_POLICIES, translation_key="dupe_policy")
            ),
        })
        return self.async_show_form(step_id="dupe_check", data_schema=schema)

    async def async_step_housekeeping(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current: dict[str, Any] = self.config_entry.options.get(CONF_HOUSEKEEPING, {})
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_HOUSEKEEPING: user_input})
        housekeeping_time = current.get(CONF_HOUSEKEEPING_TIME, "00:00:01")
        if not isinstance(housekeeping_time, str):
            # a YAML-imported entry may still have a raw datetime.time from before this was fixed
            housekeeping_time = housekeeping_time.isoformat()
        schema = vol.Schema({
            vol.Optional(CONF_HOUSEKEEPING_TIME, default=housekeeping_time): cv.string,
            vol.Optional(CONF_MEDIA_STORAGE_DAYS, default=current.get(CONF_MEDIA_STORAGE_DAYS, 7)): cv.positive_int,
        })
        return self.async_show_form(step_id="housekeeping", data_schema=schema)
