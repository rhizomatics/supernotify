"""Config flow for the Supernotify integration.

A UI setup path that reproduces examples/minimal.yaml (everything auto-discovered, no required
fields), plus options pages for the archive, dupe_check and housekeeping settings. Delivery,
transports, scenarios, recipients, cameras, action_groups, links and snooze stay YAML-only, now
under a top-level `supernotify:` key (see CONFIG_SCHEMA/async_setup in __init__.py) rather than
the legacy `notify: - platform: supernotify` block - this config entry is the sole,
unconditional owner of registering notify.supernotify in every case.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from anyio import Path
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ENABLED, CONF_NAME
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

from . import DOMAIN, MEDIA_DIR, TEMPLATE_DIR
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

_LOGGER = logging.getLogger(__name__)

_DUPE_POLICIES = [ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE]


def _event_policy_str(value: Any) -> str:
    """Render an OutcomeSelection as the pipe-separated name string parse_event_policy
    expects (e.g. "ERROR|DUPE"), whatever form it currently happens to be in.

    A YAML-imported archive config already went through ARCHIVE_SCHEMA, which turns
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
# Option values are lowercased since HA selector translation keys must match [a-z0-9-_]+ -
# the stored/parsed policy strings stay uppercase (OutcomeSelection member names).
_OUTCOME_OPTIONS = [flag.name.lower() for flag in OutcomeSelection if flag != OutcomeSelection.NONE and flag.name]


def _event_policy_to_list(value: Any) -> list[str]:
    """Turn a stored OutcomeSelection value into the list of names a multi-select needs."""
    policy_str = _event_policy_str(value)
    return [] if policy_str in ("", "NONE") else [part.lower() for part in policy_str.split("|")]


def _event_policy_from_list(values: list[str]) -> str:
    """Turn a submitted multi-select list back into the pipe-separated string
    ARCHIVE_SCHEMA's parse_event_policy expects."""
    return "|".join(value.upper() for value in values) if values else "NONE"


def extract_legacy_options(import_data: dict[str, Any]) -> dict[str, Any]:
    """Pull the archive/dupe_check/housekeeping option blocks out of a legacy YAML config dict,
    normalizing archive's event_selection/diagnostics the same way a fresh entry would.

    Shared by async_step_import (fresh entry bootstrap) and repairs.py's migration flow, which
    also needs this when merging legacy config into an entry that already exists - e.g. one
    auto-bootstrapped blank by async_setup before the interactive repair ever runs (see
    repairs.py's async_sync_entry_from_legacy_config).
    """
    archive: dict[str, Any] = dict(import_data.get(CONF_ARCHIVE) or {})
    if CONF_ARCHIVE_EVENT_SELECTION in archive:
        archive[CONF_ARCHIVE_EVENT_SELECTION] = _event_policy_str(archive[CONF_ARCHIVE_EVENT_SELECTION])
    if CONF_ARCHIVE_DIAGNOSTICS in archive:
        archive[CONF_ARCHIVE_DIAGNOSTICS] = _event_policy_str(archive[CONF_ARCHIVE_DIAGNOSTICS])

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
    return options


def extract_legacy_data(import_data: dict[str, Any]) -> dict[str, Any]:
    """Pull the template_path/media_path/media_url_prefix/mobile_discovery/recipients_discovery
    settings out of a legacy YAML config dict, defaulting anything not set - the same defaults a
    fresh entry would get. Deliberately excludes `name`, which repairs.py's
    async_sync_entry_from_legacy_config merges in separately (it isn't defaulted the same way).

    Shared by async_step_import (fresh entry bootstrap) and repairs.py's migration flow, which
    also needs this when merging legacy config into an entry that already exists - e.g. one
    auto-bootstrapped blank by async_setup before the interactive repair ever runs (see
    repairs.py's async_sync_entry_from_legacy_config). Without this, a "simple" install with
    nothing that needs a repair (no delivery/transports/scenarios/etc to move into
    supernotify.yaml) would silently keep running on defaults forever, ignoring a customized
    template_path/media_path/etc in the legacy block.
    """
    return {
        CONF_TEMPLATE_PATH: import_data.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR),
        CONF_MEDIA_PATH: import_data.get(CONF_MEDIA_PATH, MEDIA_DIR),
        CONF_MEDIA_URL_PREFIX: import_data.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media"),
        CONF_MOBILE_DISCOVERY: import_data.get(CONF_MOBILE_DISCOVERY, True),
        CONF_RECIPIENTS_DISCOVERY: import_data.get(CONF_RECIPIENTS_DISCOVERY, True),
    }


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    # cv.string, not cv.path: cv.path fails voluptuous-serialize schema conversion used by
    # the config flow frontend ("Unable to convert schema" / HTTP 500).
    defaults = defaults or {}
    return vol.Schema({
        # Determines the registered notify.<name> action (slugified) - matches the legacy
        # notify platform's `name:` YAML field, which this replaces as the sole source of truth.
        vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DOMAIN)): cv.string,
        vol.Optional(CONF_TEMPLATE_PATH, default=defaults.get(CONF_TEMPLATE_PATH, TEMPLATE_DIR)): cv.string,
        vol.Optional(CONF_MEDIA_PATH, default=defaults.get(CONF_MEDIA_PATH, MEDIA_DIR)): cv.string,
        vol.Optional(CONF_MEDIA_URL_PREFIX, default=defaults.get(CONF_MEDIA_URL_PREFIX, "/supernotify/media")): cv.string,
        vol.Optional(CONF_MOBILE_DISCOVERY, default=defaults.get(CONF_MOBILE_DISCOVERY, True)): cv.boolean,
        vol.Optional(CONF_RECIPIENTS_DISCOVERY, default=defaults.get(CONF_RECIPIENTS_DISCOVERY, True)): cv.boolean,
    })


async def _ensure_directory_exists(path_str: str) -> str | None:
    """Create a directory if it doesn't exist yet, mirroring MediaStorage.initialize()'s own
    tolerant runtime behavior (media_grab.py). Returns an error description on a genuine
    failure to create/access it, None on success."""
    try:
        path = Path(path_str)
        if not path.is_absolute():
            path = await path.absolute()
        if not await path.exists():
            await path.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as err:
        return str(err)
    return None


async def _validate_user_input(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate template_path/media_path at config-flow submission time, creating each
    directory if it doesn't exist yet. Catching a genuine failure here surfaces a typo'd or
    unwritable path immediately in the wizard, instead of leaving the user to discover it
    later via a repair issue. A blank value is left untouched - both fields are optional.
    """
    errors: dict[str, str] = {}

    template_path = user_input.get(CONF_TEMPLATE_PATH)
    if template_path:
        error = await _ensure_directory_exists(template_path)
        if error:
            errors[CONF_TEMPLATE_PATH] = "template_path_invalid"
            _LOGGER.debug("SUPERNOTIFY Invalid template_path %s: %s", template_path, error)

    media_path = user_input.get(CONF_MEDIA_PATH)
    if media_path:
        error = await _ensure_directory_exists(media_path)
        if error:
            errors[CONF_MEDIA_PATH] = "media_path_invalid"
            _LOGGER.debug("SUPERNOTIFY Invalid media_path %s: %s", media_path, error)

    return errors


class SupernotifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Supernotify config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_user_input(user_input)
            if not errors:
                return self.async_create_entry(title="Supernotify", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_user_schema(user_input), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user change the global settings of an existing entry.

        These fields are config-entry *data* (set at initial setup), not options, so HA's
        guidance is a reconfigure step rather than the options flow - which instead covers
        archive/dupe_check/housekeeping, genuine runtime preferences.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await _validate_user_input(user_input)
            if not errors:
                # async_update_and_abort, not async_update_reload_and_abort: async_setup_entry
                # registers an update listener, which async_update_entry already fires (and
                # reloads via) whenever entry.data changes - calling the "_reload" variant too
                # would reload twice and log an HA deprecation warning about the redundancy.
                return self.async_update_and_abort(entry, data_updates=user_input)
        defaults = user_input if user_input is not None else dict(entry.data)
        return self.async_show_form(step_id="reconfigure", data_schema=_user_schema(defaults), errors=errors)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Bootstrap a config entry, optionally seeded from a legacy YAML config dict.

        Two callers: __init__.py's async_setup (a from-scratch install with no entry yet) and
        async_reload_yaml_config_and_entries's bootstrap, and repairs.py's migration flow (a
        leftover legacy `notify: - platform: supernotify` block, possibly with real
        archive/housekeeping/dupe_check/name/template_path/etc already set) - both pass
        `data={}` for a genuinely fresh install, or the raw legacy config dict to preserve an
        existing installation's settings (notably `name`, which determines the registered
        notify.<name> action - see __init__.py's async_setup_entry).

        Duplicate-entry protection is the same single_config_entry manifest flag used by the
        user step (it covers SOURCE_IMPORT too), so no unique_id bookkeeping is needed here.
        """
        data: dict[str, Any] = {
            CONF_NAME: import_data.get(CONF_NAME, DOMAIN),
            **extract_legacy_data(import_data),
        }

        options = extract_legacy_options(import_data)

        _LOGGER.info(
            "SUPERNOTIFY Config entry bootstrapped (data=%s,options=%s)",
            ";".join(data.keys()),
            ";".join(options.keys()),
        )
        return self.async_create_entry(title="Supernotify", data=data, options=options)

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
            file_section = user_input["file"]
            mqtt_section = user_input["mqtt"]
            event_section = user_input["event"]
            processed = {
                CONF_ENABLED: user_input[CONF_ENABLED],
                CONF_ARCHIVE_PATH: file_section[CONF_ARCHIVE_PATH],
                CONF_ARCHIVE_DAYS: file_section[CONF_ARCHIVE_DAYS],
                CONF_ARCHIVE_PURGE_INTERVAL: file_section[CONF_ARCHIVE_PURGE_INTERVAL],
                CONF_ARCHIVE_MQTT_TOPIC: mqtt_section[CONF_ARCHIVE_MQTT_TOPIC],
                CONF_ARCHIVE_MQTT_QOS: mqtt_section[CONF_ARCHIVE_MQTT_QOS],
                CONF_ARCHIVE_MQTT_RETAIN: mqtt_section[CONF_ARCHIVE_MQTT_RETAIN],
                CONF_ARCHIVE_EVENT_NAME: event_section[CONF_ARCHIVE_EVENT_NAME],
                CONF_ARCHIVE_EVENT_SELECTION: _event_policy_from_list(event_section[CONF_ARCHIVE_EVENT_SELECTION]),
                CONF_ARCHIVE_DIAGNOSTICS: _event_policy_from_list(event_section[CONF_ARCHIVE_DIAGNOSTICS]),
            }
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_ARCHIVE: processed})
        outcome_selector = SelectSelector(
            SelectSelectorConfig(options=_OUTCOME_OPTIONS, multiple=True, translation_key="outcome_selection")
        )
        schema = vol.Schema({
            vol.Optional(CONF_ENABLED, default=False): cv.boolean,
            # section wrapper keys must be vol.Required, not vol.Optional: with Optional, the
            # frontend silently ignores both default and suggested_value for everything inside
            # (and for the rest of the form too) - https://github.com/home-assistant/frontend/issues/22419
            # No default= here - matches the working pattern in this repo's other integrations
            # (autoarm, remote_logger).
            vol.Required("file"): section(
                vol.Schema({
                    # cv.string, not cv.path: cv.path fails voluptuous-serialize schema
                    # conversion used by the config flow frontend ("Unable to convert
                    # schema" / HTTP 500).
                    vol.Optional(CONF_ARCHIVE_PATH, default=""): cv.string,
                    vol.Optional(CONF_ARCHIVE_DAYS, default=3): cv.positive_int,
                    vol.Optional(CONF_ARCHIVE_PURGE_INTERVAL, default=60): cv.positive_int,
                }),
                {"collapsed": False},
            ),
            vol.Required("mqtt"): section(
                vol.Schema({
                    vol.Optional(CONF_ARCHIVE_MQTT_TOPIC, default=""): cv.string,
                    vol.Optional(CONF_ARCHIVE_MQTT_QOS, default=0): cv.positive_int,
                    vol.Optional(CONF_ARCHIVE_MQTT_RETAIN, default=True): cv.boolean,
                }),
                {"collapsed": True},
            ),
            vol.Required("event"): section(
                vol.Schema({
                    vol.Optional(CONF_ARCHIVE_EVENT_NAME, default="supernotification"): cv.string,
                    vol.Optional(CONF_ARCHIVE_EVENT_SELECTION, default=[]): outcome_selector,
                    vol.Optional(CONF_ARCHIVE_DIAGNOSTICS, default=[]): outcome_selector,
                }),
                {"collapsed": True},
            ),
        })
        # A plain vol.Optional(default=...) only sets the server-side validation fallback -
        # once a section is present, the frontend needs description.suggested_value (for
        # every field, not just the section-nested ones) to pre-fill an existing entry's
        # current values.
        suggested_values = {
            CONF_ENABLED: current.get(CONF_ENABLED, False),
            "file": {
                CONF_ARCHIVE_PATH: current.get(CONF_ARCHIVE_PATH, ""),
                CONF_ARCHIVE_DAYS: current.get(CONF_ARCHIVE_DAYS, 3),
                CONF_ARCHIVE_PURGE_INTERVAL: current.get(CONF_ARCHIVE_PURGE_INTERVAL, 60),
            },
            "mqtt": {
                CONF_ARCHIVE_MQTT_TOPIC: current.get(CONF_ARCHIVE_MQTT_TOPIC, ""),
                CONF_ARCHIVE_MQTT_QOS: current.get(CONF_ARCHIVE_MQTT_QOS, 0),
                CONF_ARCHIVE_MQTT_RETAIN: current.get(CONF_ARCHIVE_MQTT_RETAIN, True),
            },
            "event": {
                CONF_ARCHIVE_EVENT_NAME: current.get(CONF_ARCHIVE_EVENT_NAME, "supernotification"),
                CONF_ARCHIVE_EVENT_SELECTION: _event_policy_to_list(current.get(CONF_ARCHIVE_EVENT_SELECTION, "NONE")),
                CONF_ARCHIVE_DIAGNOSTICS: _event_policy_to_list(current.get(CONF_ARCHIVE_DIAGNOSTICS, "ERROR")),
            },
        }
        schema = self.add_suggested_values_to_schema(schema, suggested_values)
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
