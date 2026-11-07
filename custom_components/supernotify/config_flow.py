"""Config flow for the Supernotify integration.

A UI setup path that reproduces examples/minimal.yaml (everything auto-discovered, no required
fields), plus options pages for the archive, dupe_check and housekeeping settings, and a
subentry per recipient. Delivery, transports, scenarios, scenario_control, cameras,
action_groups and snooze stay YAML-only, now
under a top-level `supernotify:` key (see CONFIG_SCHEMA/async_setup in __init__.py) rather than
the legacy `notify: - platform: supernotify` block - this config entry is the sole,
unconditional owner of registering notify.supernotify in every case.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from anyio import Path
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_DEBUG,
    CONF_EMAIL,
    CONF_ENABLED,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TARGET,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TargetSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from . import ARCHIVE_DIR, DOMAIN, MEDIA_DIR, TEMPLATE_DIR
from .compat import vol
from .const import (
    ATTR_CUSTOM_TARGET,
    ATTR_DUPE_POLICY_MT,
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    ATTR_EMAIL,
    ATTR_PHONE,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_EVENT_NAME,
    CONF_ARCHIVE_EVENT_SELECTION,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_CONNECTION,
    CONF_DATA,
    CONF_DEFAULT_INCLUSION,
    CONF_DELIVERY,
    CONF_DELIVERY_CONTROL,
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_DEVICE_MODEL_EXCLUDE,
    CONF_DEVICE_MODEL_INCLUDE,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_ENCRYPTION,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_INCLUSION,
    CONF_LLM_ACTION_TOOLS,
    CONF_LLM_DIAGNOSTIC_TOOLS,
    CONF_LLM_TOOLS,
    CONF_LOAD,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_MOBILE_DISCOVERY,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_PHONE_NUMBER,
    CONF_PRIORITY,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SELECTION,
    CONF_SENTENCE_COMMANDS,
    CONF_SIZE,
    CONF_TARGET_USAGE,
    CONF_TEMPLATE_PATH,
    CONF_TRANSPORT,
    CONF_TTL,
    CONF_USER_ID,
    CONF_VOICE_OCCUPANCY,
    DEFAULT_INCLUSION_VALUES,
    INCLUSION_VALUES,
    OCCUPANCY_VALUES,
    PRIORITY_VALUES,
    SUBENTRY_TYPE_RECIPIENT,
    SUBENTRY_TYPE_TRANSPORT,
    TARGET_CATEGORY_VALUES,
    TARGET_USAGE_VALUES,
    TRANSPORT_GENERIC,
)
from .hass_api import HomeAssistantAPI
from .options import (
    OPTION_DEVICE_DISCOVERY,
    OPTION_DEVICE_DOMAIN,
    OPTION_DEVICE_MODEL_SELECT,
    SELECT_EXCLUDE,
    SELECT_INCLUDE,
)
from .people import PeopleRegistry, recipient_key
from .schema import RECIPIENT_DELIVERY_SCHEMA, RECIPIENT_SCHEMA, TRANSPORT_SCHEMA, OutcomeSelection
from .target import Target

if TYPE_CHECKING:
    from .transport import Transport

_LOGGER = logging.getLogger(__name__)

# the recipient form's collapsible section holding its delivery overrides
SECTION_DELIVERY_OVERRIDES = "delivery_overrides"

_DUPE_POLICIES = [ATTR_DUPE_POLICY_MTSLP, ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE]

# Linked from the options pages that have their own documentation page - the "?" help icon can only
# link to the manifest's one documentation URL
ARCHIVE_DOCS_URL = "https://supernotify.rhizomatics.org.uk/latest/configuration/archiving/"
DUPE_CHECK_DOCS_URL = "https://supernotify.rhizomatics.org.uk/latest/configuration/dupe_detection/"
PEOPLE_DOCS_URL = "https://supernotify.rhizomatics.org.uk/latest/configuration/people/"
TRANSPORTS_DOCS_URL = "https://supernotify.rhizomatics.org.uk/latest/transports/"
# the transport form's field for the delivery defaults it has no field of its own for, and
# those it does
ATTR_OTHER_DELIVERY_DEFAULTS = "other_delivery_defaults"
_TYPED_DELIVERY_DEFAULTS = (
    CONF_DEBUG,
    CONF_ACTION,
    CONF_TARGET_USAGE,
    CONF_OPTIONS,
    CONF_DATA,
    CONF_INCLUSION,
    CONF_PRIORITY,
)
# the transport form's section for settings seldom changed
SECTION_ADVANCED = "advanced"

# The Delivery Control choices meaning "not set", which leave deliveries with their transport's own
# default - never stored, the option is left out instead
NOT_SET_INCLUSION = "transport"
NOT_SET_OCCUPANCY = "not_controlled"


def _event_policy_str(value: Any) -> str:  # ruff: ignore[any-type]
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
_OUTCOME_OPTIONS = [flag.name.lower() for flag in OutcomeSelection if flag != OutcomeSelection.NONE and flag.name is not None]


def _event_policy_to_list(value: str) -> list[str]:
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

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_RECIPIENT: RecipientSubentryFlow, SUBENTRY_TYPE_TRANSPORT: TransportSubentryFlow}


class SupernotifyOptionsFlow(OptionsFlow):
    """Options pages for archive, dupe_check, housekeeping and LLM tools settings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["archive", "dupe_check", "housekeeping", "delivery_control", "llm_tools"]
        )

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
                    vol.Optional(CONF_ARCHIVE_PATH, default=ARCHIVE_DIR): cv.string,
                    vol.Optional(CONF_ARCHIVE_DAYS, default=3): cv.positive_int,
                }),
                {"collapsed": False},
            ),
            vol.Required("mqtt"): section(
                vol.Schema({
                    vol.Optional(CONF_ARCHIVE_MQTT_TOPIC, default=""): cv.string,
                    vol.Optional(CONF_ARCHIVE_MQTT_QOS, default=0): cv.positive_int,
                    vol.Optional(CONF_ARCHIVE_MQTT_RETAIN, default=False): cv.boolean,
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
                CONF_ARCHIVE_PATH: current.get(CONF_ARCHIVE_PATH, ARCHIVE_DIR),
                CONF_ARCHIVE_DAYS: current.get(CONF_ARCHIVE_DAYS, 3),
            },
            "mqtt": {
                CONF_ARCHIVE_MQTT_TOPIC: current.get(CONF_ARCHIVE_MQTT_TOPIC, ""),
                CONF_ARCHIVE_MQTT_QOS: current.get(CONF_ARCHIVE_MQTT_QOS, 0),
                CONF_ARCHIVE_MQTT_RETAIN: current.get(CONF_ARCHIVE_MQTT_RETAIN, False),
            },
            "event": {
                CONF_ARCHIVE_EVENT_NAME: current.get(CONF_ARCHIVE_EVENT_NAME, "supernotification"),
                CONF_ARCHIVE_EVENT_SELECTION: _event_policy_to_list(current.get(CONF_ARCHIVE_EVENT_SELECTION, "NONE")),
                CONF_ARCHIVE_DIAGNOSTICS: _event_policy_to_list(current.get(CONF_ARCHIVE_DIAGNOSTICS, "ERROR")),
            },
        }
        schema = self.add_suggested_values_to_schema(schema, suggested_values)
        return self.async_show_form(
            step_id="archive", data_schema=schema, description_placeholders={"learn_more_url": ARCHIVE_DOCS_URL}
        )

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
        return self.async_show_form(
            step_id="dupe_check", data_schema=schema, description_placeholders={"learn_more_url": DUPE_CHECK_DOCS_URL}
        )

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

    async def async_step_delivery_control(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Defaults for deliveries that don't set their own - inclusion, and occupancy for spoken
        deliveries"""
        current: dict[str, Any] = self.config_entry.options.get(CONF_DELIVERY_CONTROL, {})
        if user_input is not None:
            control: dict[str, Any] = {}
            if user_input[CONF_DEFAULT_INCLUSION] != NOT_SET_INCLUSION:
                control[CONF_DEFAULT_INCLUSION] = user_input[CONF_DEFAULT_INCLUSION]
            if user_input[CONF_VOICE_OCCUPANCY] != NOT_SET_OCCUPANCY:
                control[CONF_VOICE_OCCUPANCY] = user_input[CONF_VOICE_OCCUPANCY]
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_DELIVERY_CONTROL: control})
        schema = vol.Schema({
            vol.Optional(
                CONF_DEFAULT_INCLUSION, default=current.get(CONF_DEFAULT_INCLUSION, NOT_SET_INCLUSION)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[NOT_SET_INCLUSION, *DEFAULT_INCLUSION_VALUES], translation_key=CONF_DEFAULT_INCLUSION
                )
            ),
            vol.Optional(CONF_VOICE_OCCUPANCY, default=current.get(CONF_VOICE_OCCUPANCY, NOT_SET_OCCUPANCY)): SelectSelector(
                SelectSelectorConfig(options=[NOT_SET_OCCUPANCY, *OCCUPANCY_VALUES], translation_key=CONF_VOICE_OCCUPANCY)
            ),
        })
        return self.async_show_form(step_id="delivery_control", data_schema=schema)

    async def async_step_llm_tools(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Which tools llm.py offers to AI conversation agents and the MCP server, and whether
        sentences.py registers commands with the built-in agent"""
        current: dict[str, Any] = self.config_entry.options.get(CONF_LLM_TOOLS, {})
        if user_input is not None:
            return self.async_create_entry(title="", data={**self.config_entry.options, CONF_LLM_TOOLS: user_input})
        schema = vol.Schema({
            vol.Optional(CONF_LLM_ACTION_TOOLS, default=current.get(CONF_LLM_ACTION_TOOLS, False)): cv.boolean,
            vol.Optional(CONF_LLM_DIAGNOSTIC_TOOLS, default=current.get(CONF_LLM_DIAGNOSTIC_TOOLS, False)): cv.boolean,
            vol.Optional(CONF_SENTENCE_COMMANDS, default=current.get(CONF_SENTENCE_COMMANDS, False)): cv.boolean,
        })
        return self.async_show_form(step_id="llm_tools", data_schema=schema)


# The target categories the target selector gives, as in supernotify.notify - anything else is
# a custom target, entered as text
_SELECTOR_TARGET_CATEGORIES = (ATTR_ENTITY_ID, ATTR_DEVICE_ID, ATTR_AREA_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID)
# Custom targets recognised without a "category:" prefix
_PLAIN_CUSTOM_CATEGORIES = (ATTR_EMAIL, ATTR_PHONE)


def target_from_fields(selected: dict[str, Any] | None, custom: list[str] | None) -> dict[str, list[str]]:
    """Build a recipient target from the target selector and custom target fields, the same
    pair supernotify.notify offers. A custom target is a "category:value", whose value passes the
    category's own check where it's one of TARGET_CATEGORY_VALUES, or an e-mail address or phone
    number on its own. Raises vol.Invalid for one that is neither."""
    target: dict[str, list[str]] = {}
    for category, values in (selected or {}).items():
        if found := [str(v) for v in cv.ensure_list(values) if v]:
            target[category] = found
    for value in custom or []:
        value = value.strip()
        if not value:
            continue
        prefix, sep, rest = value.partition(":")
        if sep and rest and not rest.startswith("/") and prefix == slugify(prefix):
            category, value = prefix, rest
            # a custom category, for a generic transport, is left as it is
            if category in TARGET_CATEGORY_VALUES and (check := getattr(Target, f"is_{category}", None)) and not check(value):
                raise vol.Invalid(f"not a valid {category}: {value}")
        else:
            category = next(iter(Target([value]).targets))
            if category not in _PLAIN_CUSTOM_CATEGORIES:
                raise vol.Invalid(f"unrecognised custom target {value}")
        target.setdefault(category, [])
        if value not in target[category]:
            target[category].append(value)
    return target


def target_to_fields(target: Any) -> tuple[dict[str, list[str]], list[str]]:  # ruff: ignore[any-type]
    """Split a recipient target back into the target selector and custom target fields"""
    as_dict: dict[str, list[str]] = Target(target).as_dict() if target else {}
    selected: dict[str, list[str]] = {}
    custom: list[str] = []
    for category, values in as_dict.items():
        if category in _SELECTOR_TARGET_CATEGORIES:
            selected[category] = list(values)
        elif category in _PLAIN_CUSTOM_CATEGORIES:
            custom.extend(values)
        else:
            custom.extend(f"{category}:{v}" for v in values)
    return selected, custom


class RecipientSubentryFlow(ConfigSubentryFlow):
    """Add or change a recipient - who, how to reach them, which of their mobile devices to
    use, and how individual deliveries treat them.

    The recipient is held in RECIPIENT_SCHEMA shape as the steps go, and saved from the menu.
    A recipient adds to, or overrides, the one discovered for the same person or user.
    """

    def __init__(self) -> None:
        self._recipient: dict[str, Any] = {}
        # the new recipient's subentry unique_id, from recipient_key()
        self._key: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Who the recipient is - a person, a user with no person, or by name, someone who isn't a
        Home Assistant user. Those discovered are recipients already, so this is mostly for the last"""
        errors: dict[str, str] = {}
        if user_input is not None:
            key = recipient_key(user_input)
            if not key:
                errors["base"] = "person_or_user_required"
            elif any(s.unique_id == key for s in self._get_entry().subentries.values()):
                return self.async_abort(reason="already_configured")
            else:
                self._key = key
                self._recipient = {k: v for k, v in user_input.items() if v}
                # a person's own user, which Home Assistant keeps on the person
                if (person := self._recipient.get(CONF_PERSON)) and CONF_USER_ID not in self._recipient:
                    state = self.hass.states.get(person)
                    if state and isinstance(user_id := state.attributes.get(CONF_USER_ID), str):
                        self._recipient[CONF_USER_ID] = user_id
                # only a Home Assistant user has mobile app devices
                has_user = CONF_PERSON in self._recipient or CONF_USER_ID in self._recipient
                self._recipient[CONF_MOBILE_DISCOVERY] = has_user and self._mobile_discovery_default()
                return await self.async_step_details()
        users = await HomeAssistantAPI(self.hass).async_real_user_ids()
        schema = vol.Schema({
            vol.Optional(CONF_PERSON): EntitySelector(EntitySelectorConfig(domain="person")),
            vol.Optional(CONF_USER_ID): SelectSelector(
                SelectSelectorConfig(options=[SelectOptionDict(value=k, label=v) for k, v in users.items()])
            ),
            vol.Optional(CONF_ALIAS): TextSelector(),
        })
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors, description_placeholders={"learn_more_url": PEOPLE_DOCS_URL}
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        self._recipient = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_details()

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """How to reach the recipient, and which of their mobile devices to use"""
        errors: dict[str, str] = {}
        devices = self._mobile_device_options()
        if user_input is not None:
            try:
                target = target_from_fields(user_input.get(CONF_TARGET), user_input.get(ATTR_CUSTOM_TARGET))
            except vol.Invalid:
                errors[ATTR_CUSTOM_TARGET] = "invalid_custom_target"
            try:
                delivery = RECIPIENT_DELIVERY_SCHEMA(user_input.get(SECTION_DELIVERY_OVERRIDES, {}).get(CONF_DELIVERY) or {})
            except vol.Invalid:
                errors["base"] = "invalid_delivery"
            if not errors:
                # the alias is who someone that isn't a Home Assistant user is, so can't be left blank
                has_user = CONF_PERSON in self._recipient or CONF_USER_ID in self._recipient
                for key in (CONF_ALIAS, CONF_EMAIL, CONF_PHONE_NUMBER):
                    if user_input.get(key):
                        self._recipient[key] = user_input[key]
                    elif key != CONF_ALIAS or has_user:
                        self._recipient.pop(key, None)
                self._recipient[CONF_ENABLED] = user_input[CONF_ENABLED]
                self._recipient[CONF_MOBILE_DISCOVERY] = user_input[CONF_MOBILE_DISCOVERY]
                for key, value in ((CONF_TARGET, target), (CONF_DELIVERY, delivery)):
                    if value:
                        self._recipient[key] = value
                    else:
                        self._recipient.pop(key, None)
                selected = user_input.get(CONF_MOBILE_DEVICES, [])
                self._recipient[CONF_MOBILE_DEVICES] = [
                    {CONF_MOBILE_APP_ID: d["value"], CONF_ENABLED: d["value"] in selected} for d in devices
                ]
                return await self.async_step_save()

        selected_target, custom_target = target_to_fields(self._recipient.get(CONF_TARGET))
        disabled = {
            d.get(CONF_MOBILE_APP_ID) for d in self._recipient.get(CONF_MOBILE_DEVICES, []) if not d.get(CONF_ENABLED, True)
        }
        schema = vol.Schema({
            vol.Optional(CONF_ALIAS): TextSelector(),
            vol.Optional(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
            vol.Optional(CONF_PHONE_NUMBER): TextSelector(TextSelectorConfig(type=TextSelectorType.TEL)),
            vol.Optional(CONF_ENABLED, default=True): cv.boolean,
            vol.Optional(CONF_MOBILE_DISCOVERY, default=True): cv.boolean,
            vol.Optional(CONF_MOBILE_DEVICES): SelectSelector(SelectSelectorConfig(options=devices, multiple=True)),
            vol.Optional(CONF_TARGET): TargetSelector(),
            vol.Optional(ATTR_CUSTOM_TARGET): TextSelector(TextSelectorConfig(multiple=True)),
            vol.Optional(SECTION_DELIVERY_OVERRIDES, default=dict): section(
                vol.Schema({vol.Optional(CONF_DELIVERY): ObjectSelector()}),
                {"collapsed": not (self._recipient.get(CONF_DELIVERY) or errors.get("base"))},
            ),
        })
        suggested = {
            CONF_ALIAS: self._recipient.get(CONF_ALIAS),
            CONF_EMAIL: self._recipient.get(CONF_EMAIL),
            CONF_PHONE_NUMBER: self._recipient.get(CONF_PHONE_NUMBER),
            CONF_ENABLED: self._recipient.get(CONF_ENABLED, True),
            CONF_MOBILE_DISCOVERY: self._recipient.get(CONF_MOBILE_DISCOVERY, self._mobile_discovery_default()),
            CONF_MOBILE_DEVICES: [d["value"] for d in devices if d["value"] not in disabled],
            CONF_TARGET: selected_target or None,
            ATTR_CUSTOM_TARGET: custom_target or None,
            SECTION_DELIVERY_OVERRIDES: {CONF_DELIVERY: self._recipient.get(CONF_DELIVERY) or None},
        }
        return self.async_show_form(
            step_id="details",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={
                "recipient": self._title(),
                "learn_more_url": PEOPLE_DOCS_URL,
                "deliveries": ", ".join(self._delivery_names()) or "-",
                "categories": ", ".join(TARGET_CATEGORY_VALUES),
            },
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        RECIPIENT_SCHEMA(self._recipient)  # anything the steps let through that it wouldn't is a bug here
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), data=self._recipient, title=self._title()
            )
        return self.async_create_entry(
            title=self._title(),
            data=self._recipient,
            unique_id=self._key,
        )

    def _mobile_discovery_default(self) -> bool:
        """The integration's own setting, which a recipient without one of their own follows"""
        return bool(self._get_entry().data.get(CONF_MOBILE_DISCOVERY, True))

    def _title(self) -> str:
        """The alias, else the person's name, else the user's"""
        if alias := self._recipient.get(CONF_ALIAS):
            return str(alias)
        if (person := self._recipient.get(CONF_PERSON)) and (state := self.hass.states.get(person)):
            return state.name
        return str(self._recipient.get(CONF_PERSON) or self._recipient.get(CONF_USER_ID))

    def _mobile_device_options(self) -> list[SelectOptionDict]:
        """The recipient's discovered mobile devices that can be notified, and any already
        configured for them that weren't discovered"""
        hass_api = HomeAssistantAPI(self.hass)
        hass_api.build_mobile_app_cache()
        registry = PeopleRegistry([], hass_api)
        user_id = self._recipient.get(CONF_USER_ID)
        person = self._recipient.get(CONF_PERSON)
        if user_id:
            discovered = registry.mobile_devices_for_user(user_id)
        elif person:
            discovered = registry.mobile_devices_for_person(person)
        else:
            discovered = []
        options = {
            d.mobile_app_id: SelectOptionDict(value=d.mobile_app_id, label=d.device_name or d.mobile_app_id)
            for d in discovered
            if d.mobile_app_id and d.action
        }
        for d in self._recipient.get(CONF_MOBILE_DEVICES, []):
            app_id = d.get(CONF_MOBILE_APP_ID)
            if app_id and app_id not in options:
                options[app_id] = SelectOptionDict(value=app_id, label=app_id)
        return list(options.values())

    def _delivery_names(self) -> list[str]:
        """The running deliveries, to list for the delivery field"""
        engine = getattr(self._get_entry(), "runtime_data", None)
        return sorted(engine.context.delivery_registry.deliveries) if engine is not None else []


class TransportSubentryFlow(ConfigSubentryFlow):
    """Add or change a transport - whether it's used, and the defaults for its deliveries.

    Every transport in use is listed already, so adding one is for those needing configuration
    before they can be used, like generic's action or chime's aliases. The transport is held as
    it would be written in YAML under `transports:`, and saved as that.
    """

    def __init__(self) -> None:
        self._name: str = ""
        self._transport: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Which transport, of those not listed already whose integration is here"""
        addable = self._addable()
        if not addable:
            return self.async_abort(reason="no_transports")
        if user_input is not None:
            self._name = user_input[CONF_TRANSPORT]
            return await self.async_step_details()
        schema = vol.Schema({vol.Required(CONF_TRANSPORT): SelectSelector(SelectSelectorConfig(options=addable))})
        return self.async_show_form(
            step_id="user", data_schema=schema, description_placeholders={"learn_more_url": TRANSPORTS_DOCS_URL}
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        subentry = self._get_reconfigure_subentry()
        self._name = str(subentry.unique_id)
        self._transport = dict(subentry.data)
        return await self.async_step_details()

    async def async_step_details(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Whether the transport is used, the defaults for its deliveries, and its connection"""
        errors: dict[str, str] = {}
        error = ""
        # deprecated settings are shown, and saved, as their replacements
        defaults: dict[str, Any] = dict(_migrate_deprecated(self._transport).get(CONF_DELIVERY_DEFAULTS) or {})
        if user_input is not None:
            given: dict[str, Any] = user_input.get(CONF_DELIVERY_DEFAULTS, {})
            other = given.get(ATTR_OTHER_DELIVERY_DEFAULTS) or {}
            try:
                target = target_from_fields(given.get(CONF_TARGET), given.get(ATTR_CUSTOM_TARGET))
            except vol.Invalid:
                errors["base"] = "invalid_custom_target"
            if not isinstance(other, dict):
                errors["base"] = "invalid_transport"
                error = str(other)
            if not errors:
                # a field left empty leaves the same setting in the other delivery defaults alone
                defaults = dict(other)
                for key in _TYPED_DELIVERY_DEFAULTS:
                    if given.get(key):
                        defaults[key] = given[key]
                if target:
                    defaults[CONF_TARGET] = target
                transport = {
                    k: v
                    for k, v in _migrate_deprecated(self._transport).items()
                    if k not in (CONF_ALIAS, CONF_ENABLED, CONF_LOAD, CONF_DELIVERY_DEFAULTS, CONF_CONNECTION)
                }
                transport[CONF_ENABLED] = user_input[CONF_ENABLED]
                transport[CONF_LOAD] = user_input.get(SECTION_ADVANCED, {}).get(CONF_LOAD, True)
                for key, value in (
                    (CONF_ALIAS, user_input.get(CONF_ALIAS)),
                    (CONF_DELIVERY_DEFAULTS, defaults),
                    (CONF_CONNECTION, self._connection(user_input.get(CONF_CONNECTION))),
                ):
                    if value:
                        transport[key] = value
                try:
                    TRANSPORT_SCHEMA(transport)
                except vol.Invalid as err:
                    errors["base"] = "invalid_transport"
                    error = str(err)
                else:
                    self._transport = transport
                    return await self.async_step_save()

        selected_target, custom_target = target_to_fields(defaults.get(CONF_TARGET))
        transport_class = self._transport_class()
        fields: dict[Any, Any] = {
            vol.Optional(CONF_ENABLED, default=True): cv.boolean,
            vol.Optional(CONF_ALIAS): TextSelector(),
        }
        default_fields: dict[Any, Any] = {vol.Optional(CONF_DEBUG): cv.boolean}
        if self._takes_action():
            default_fields[vol.Optional(CONF_ACTION)] = TextSelector()
        default_fields.update({
            # above the targets, as it says how they're used
            vol.Optional(CONF_TARGET_USAGE): SelectSelector(
                SelectSelectorConfig(options=TARGET_USAGE_VALUES, translation_key=CONF_TARGET_USAGE)
            ),
            vol.Optional(CONF_TARGET): TargetSelector(),
            vol.Optional(ATTR_CUSTOM_TARGET): TextSelector(TextSelectorConfig(multiple=True)),
            vol.Optional(CONF_OPTIONS): ObjectSelector(),
            vol.Optional(CONF_DATA): ObjectSelector(),
            vol.Optional(CONF_INCLUSION): SelectSelector(SelectSelectorConfig(options=INCLUSION_VALUES, multiple=True)),
            # custom values, as YAML can give a priority as a number
            vol.Optional(CONF_PRIORITY): SelectSelector(
                SelectSelectorConfig(options=list(PRIORITY_VALUES), multiple=True, custom_value=True)
            ),
            vol.Optional(ATTR_OTHER_DELIVERY_DEFAULTS): ObjectSelector(),
        })
        fields[vol.Optional(CONF_DELIVERY_DEFAULTS, default=dict)] = section(vol.Schema(default_fields), {"collapsed": False})
        load = self._transport.get(CONF_LOAD, True)
        fields[vol.Optional(SECTION_ADVANCED, default=dict)] = section(
            vol.Schema({vol.Optional(CONF_LOAD, default=True): cv.boolean}), {"collapsed": bool(load)}
        )
        connection: dict[str, Any] = dict(self._transport.get(CONF_CONNECTION) or {})
        if transport_class is not None and transport_class.uses_connection:
            fields[vol.Optional(CONF_CONNECTION, default=dict)] = section(
                vol.Schema({
                    vol.Optional(CONF_HOST): TextSelector(),
                    vol.Optional(CONF_PORT): NumberSelector(
                        NumberSelectorConfig(min=1, max=65535, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(CONF_ENCRYPTION): SelectSelector(
                        SelectSelectorConfig(options=["tls", "starttls", "none"], translation_key="connection_encryption")
                    ),
                    vol.Optional(CONF_USERNAME): TextSelector(),
                    # never shown, and left empty to keep the one there is
                    vol.Optional(CONF_PASSWORD): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                    vol.Optional(CONF_TIMEOUT): NumberSelector(NumberSelectorConfig(min=1, mode=NumberSelectorMode.BOX)),
                    vol.Optional(CONF_VERIFY_SSL): cv.boolean,
                }),
                {"collapsed": not connection},
            )
        suggested = {
            CONF_ENABLED: self._transport.get(CONF_ENABLED, True),
            SECTION_ADVANCED: {CONF_LOAD: load},
            CONF_ALIAS: self._transport.get(CONF_ALIAS),
            CONF_DELIVERY_DEFAULTS: {
                CONF_ACTION: defaults.get(CONF_ACTION),
                CONF_TARGET: selected_target or None,
                ATTR_CUSTOM_TARGET: custom_target or None,
                CONF_OPTIONS: defaults.get(CONF_OPTIONS),
                CONF_DATA: defaults.get(CONF_DATA),
                CONF_INCLUSION: cv.ensure_list(defaults.get(CONF_INCLUSION)) or None,
                CONF_PRIORITY: [str(p) for p in cv.ensure_list(defaults.get(CONF_PRIORITY))] or None,
                CONF_DEBUG: defaults.get(CONF_DEBUG, False),
                CONF_TARGET_USAGE: defaults.get(CONF_TARGET_USAGE),
                ATTR_OTHER_DELIVERY_DEFAULTS: {
                    k: v for k, v in defaults.items() if k not in (*_TYPED_DELIVERY_DEFAULTS, CONF_TARGET)
                }
                or None,
            },
            CONF_CONNECTION: {k: v for k, v in connection.items() if k != CONF_PASSWORD},
        }
        return self.async_show_form(
            step_id="details",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(fields), suggested),
            errors=errors,
            description_placeholders={
                "transport": self._title(),
                "learn_more_url": f"{TRANSPORTS_DOCS_URL}{self._name}/",
                "categories": ", ".join(TARGET_CATEGORY_VALUES),
                "error": error,
            },
        )

    def _connection(self, given: dict[str, Any] | None) -> dict[str, Any]:
        """The connection as entered, the numbers as whole numbers, and with the password kept
        when it's left empty"""
        connection = {k: int(v) if isinstance(v, float) else v for k, v in (given or {}).items() if v not in (None, "")}
        if CONF_PASSWORD not in connection and (password := (self._transport.get(CONF_CONNECTION) or {}).get(CONF_PASSWORD)):
            connection[CONF_PASSWORD] = password
        return connection

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_and_abort(
                self._get_entry(), self._get_reconfigure_subentry(), data=self._transport, title=self._title()
            )
        return self.async_create_entry(title=self._title(), data=self._transport, unique_id=self._name)

    def _title(self) -> str:
        return str(self._transport.get(CONF_ALIAS) or self._name)

    def _transport_class(self) -> type[Transport] | None:
        from .static_config import TRANSPORTS

        return next((t for t in TRANSPORTS if t.name == self._name), None)

    def _takes_action(self) -> bool:
        """Whether the transport's action is configured, rather than fixed or found for it"""
        transport_class = self._transport_class()
        return transport_class is not None and (transport_class.action_configured or self._name == TRANSPORT_GENERIC)

    def _addable(self) -> list[str]:
        """The transports not listed already, whose integration, if they need one, is here"""
        from .static_config import TRANSPORTS

        listed = {s.unique_id for s in self._get_entry().subentries.values() if s.subentry_type == SUBENTRY_TYPE_TRANSPORT}
        hass_api = HomeAssistantAPI(self.hass)
        return sorted(
            t.name
            for t in TRANSPORTS
            if t.name not in listed and (t.integration_domain is None or hass_api.integration_loaded(t.integration_domain))
        )


def _migrate_deprecated(transport: dict[str, Any]) -> dict[str, Any]:
    """A transport's configuration with its deprecated settings moved to their replacements, as
    model.TransportConfig applies them - device_domain, device_discovery and device_model_include/
    exclude to its options, and its delivery defaults' selection to inclusion"""
    migrated = {
        k: v
        for k, v in transport.items()
        if k not in (CONF_DEVICE_DOMAIN, CONF_DEVICE_DISCOVERY, CONF_DEVICE_MODEL_INCLUDE, CONF_DEVICE_MODEL_EXCLUDE)
    }
    defaults: dict[str, Any] = dict(transport.get(CONF_DELIVERY_DEFAULTS) or {})
    options: dict[str, Any] = dict(defaults.get(CONF_OPTIONS) or {})
    if CONF_DEVICE_DOMAIN in transport:
        options[OPTION_DEVICE_DOMAIN] = transport[CONF_DEVICE_DOMAIN]
    if CONF_DEVICE_MODEL_INCLUDE in transport or CONF_DEVICE_MODEL_EXCLUDE in transport:
        options[OPTION_DEVICE_MODEL_SELECT] = {
            SELECT_INCLUDE: transport.get(CONF_DEVICE_MODEL_INCLUDE),
            SELECT_EXCLUDE: transport.get(CONF_DEVICE_MODEL_EXCLUDE),
        }
    if CONF_DEVICE_DISCOVERY in transport and options.get(OPTION_DEVICE_DISCOVERY) is None:
        options[OPTION_DEVICE_DISCOVERY] = transport[CONF_DEVICE_DISCOVERY]
    if CONF_SELECTION in defaults:
        selection = defaults.pop(CONF_SELECTION)
        defaults.setdefault(CONF_INCLUSION, selection)
    if options:
        defaults[CONF_OPTIONS] = options
    if defaults:
        migrated[CONF_DELIVERY_DEFAULTS] = defaults
    return migrated
