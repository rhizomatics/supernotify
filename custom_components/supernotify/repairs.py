"""Repairs for supernotify's legacy `notify: - platform: supernotify` YAML block.

The config entry is the sole, unconditional owner of registering notify.supernotify (see
async_setup_entry in __init__.py) - delivery/transports/scenarios/recipients/cameras/
action_groups/links/snooze now live under a top-level `supernotify:` YAML key instead (see
CONFIG_SCHEMA/async_setup in __init__.py). A leftover legacy block is inert (notify.py's
async_get_service shim registers nothing from it) but still raises this fixable repair, which
automates moving that config into `supernotify.yaml` plus a `supernotify: !include
supernotify.yaml` line in configuration.yaml.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config import async_check_ha_config_file
from homeassistant.const import CONF_NAME
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.yaml import Secrets, load_yaml_dict, save_yaml

from . import DOMAIN, async_reload_yaml_config_and_entries
from .config_flow import extract_legacy_data, extract_legacy_options
from .const import (
    CONF_ACTION_GROUPS,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_LINKS,
    CONF_RECIPIENTS,
    CONF_SCENARIOS,
    CONF_SNOOZE,
    CONF_TRANSPORTS,
)
from .schema import SUPERNOTIFY_YAML_SCHEMA

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult

    # RepairsFlowResult isn't exported on every supported HA version (it's just
    # FlowResult[FlowContext, str] under the hood) - FlowResult itself is a much older, more
    # stable export, so use that directly rather than depending on the alias's presence.
    RepairsFlowResult = FlowResult

_LOGGER = logging.getLogger(__name__)

ISSUE_ID = "legacy_yaml_config"
# Raised whenever the automated migration can't proceed for any reason (invalid config
# before we'd even touch it, a write failure, or a post-write validation failure that got
# rolled back) - a separate, persistent (non-fixable) issue so the need for a manual migration
# survives closing the confirm-step dialog, distinct from ISSUE_ID (which stays fixable/
# retryable - e.g. after the user manually clears whatever blocked the automated attempt).
MANUAL_MIGRATION_ISSUE_ID = "legacy_yaml_manual_migration_required"
SUPERNOTIFY_YAML_FILENAME = "supernotify.yaml"
CONFIGURATION_YAML_FILENAME = "configuration.yaml"

_MANUAL_MIGRATION_REASONS: dict[str, str] = {
    "baseline_invalid": ("configuration.yaml already has an unrelated problem, so it's not safe to edit automatically"),
    "supernotify_yaml_exists": "a supernotify.yaml file already exists",
    "configuration_yaml_unreadable": "configuration.yaml could not be read",
    "supernotify_key_exists": "configuration.yaml already has a top-level supernotify: key",
    "migrated_config_invalid": "the legacy configuration itself doesn't pass validation",
    "write_failed": "writing the new configuration files failed",
    "validation_failed": "the updated configuration.yaml failed validation and was rolled back",
}

# The 8 keys migrated out of the legacy notify: platform block, matching schema.py's
# SUPERNOTIFY_YAML_SCHEMA.
_YAML_ONLY_KEYS = (
    CONF_DELIVERY,
    CONF_TRANSPORTS,
    CONF_SCENARIOS,
    CONF_RECIPIENTS,
    CONF_CAMERAS,
    CONF_ACTION_GROUPS,
    CONF_LINKS,
    CONF_SNOOZE,
)


def async_sync_entry_from_legacy_config(hass: HomeAssistant, legacy_config: dict[str, Any]) -> None:
    """As long as the legacy `notify: - platform: supernotify` block exists, it stays
    authoritative for the owning entry's name/template_path/media_path/etc and
    archive/dupe_check/housekeeping settings - synced onto the entry on every load (not gated
    behind the interactive migration flow), matching what the legacy platform loader itself
    always did for `name:` (slugify(name or "notify") determined the service - see
    homeassistant.components.notify.legacy.async_setup_legacy).

    Without this, an entry auto-bootstrapped blank by async_setup (see __init__.py) - which
    happens before anyone gets around to opening and confirming the migration repair, and is the
    only entry that will ever exist for a "simple" install with nothing that needs that repair -
    would keep running on defaults forever: wrong service name, ignored template_path/media_path,
    archive disabled, no dupe_check/housekeeping, silently breaking automations and archiving on
    every restart.

    Deliberately a single async_update_entry call rather than one per field group: that call
    notifies the entry's update listener (which reloads it) via a task, and Python's eager task
    execution can start running that task immediately and synchronously - reaching as far as
    unloading the entry (which removes its update listener) before a second, separate
    async_update_entry call made moments later in the same batch gets a chance to run. That
    second call then finds no listener left to notify and silently no-ops, so only the FIRST of
    several back-to-back calls ever actually reloads - permanently losing whatever the others
    carried, even though entry.data/entry.options themselves end up fully correct (e.g. the
    Reconfigure screen reads right) while the *running* service silently keeps stale defaults.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return
    entry = entries[0]

    data = dict(entry.data)
    legacy_name = legacy_config.get(CONF_NAME)
    if legacy_name:
        data[CONF_NAME] = legacy_name
    data.update(extract_legacy_data(legacy_config))

    options = {**entry.options, **extract_legacy_options(legacy_config)}

    if data != entry.data or options != entry.options:
        hass.config_entries.async_update_entry(entry, data=data, options=options)


def async_create_legacy_yaml_issue(hass: HomeAssistant, legacy_config: dict[str, Any]) -> None:
    """Raise (or refresh) the fixable repair for a leftover legacy notify: platform block."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ID,
        # issue data must be flat str/int/float/None - the raw legacy config (still just plain
        # YAML-parsed data, since notify.py's shim never runs it through any schema) is nested,
        # so it's carried through as a JSON string and decoded back in async_create_fix_flow.
        data={"legacy_config": json.dumps(legacy_config, default=str)},
    )


def _extract_yaml_only_config(legacy_config: dict[str, Any]) -> dict[str, Any]:
    return {key: legacy_config[key] for key in _YAML_ONLY_KEYS if legacy_config.get(key)}


def _async_get_migration_lock(hass: HomeAssistant) -> asyncio.Lock:
    """A lock guarding the file-write-and-reload critical section below, distinct from a
    ConfigEntry's own setup_lock (which HA already uses internally to serialize a single
    entry's own setup/reload/unload) - this instead prevents two concurrent attempts at this
    flow (e.g. a double submit, or two admin sessions) from interleaving their file writes."""
    return hass.data.setdefault(DOMAIN, {}).setdefault("migration_lock", asyncio.Lock())


def _load_configuration_yaml_dict(hass: HomeAssistant) -> dict[str, Any]:
    """Parse configuration.yaml, resolving !secret references.

    Without a Secrets object, load_yaml_dict raises HomeAssistantError("Secrets not supported
    in this YAML file") on ANY file containing a `!secret` tag anywhere - extremely common in
    real configs - which a caller catching that as "parse failed" would otherwise silently
    misread as e.g. "not migrated yet" on every single load.
    """
    return load_yaml_dict(
        hass.config.path(CONFIGURATION_YAML_FILENAME),
        Secrets(Path(hass.config.config_dir)),
    )


def _is_already_migrated(hass: HomeAssistant) -> bool:
    """A prior run of this same flow already wrote both files - only remains true until the
    user removes the now-dead legacy notify: block (which stops notify.py from re-raising the
    issue at all)."""
    if not os.path.exists(hass.config.path(SUPERNOTIFY_YAML_FILENAME)):
        return False
    try:
        parsed = _load_configuration_yaml_dict(hass)
    except Exception:
        return False
    return DOMAIN in parsed


class SupernotifyLegacyYamlRepairFlow(RepairsFlow):
    """Migrate delivery/transports/scenarios/recipients/cameras/action_groups/links/snooze out
    of the legacy `notify: - platform: supernotify` YAML block into a new top-level
    `supernotify:` key (typically `supernotify: !include supernotify.yaml`).
    """

    def __init__(self, legacy_config: dict[str, Any]) -> None:
        self._legacy_config = legacy_config
        self._original_configuration_yaml: str | None = None

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        if await self.hass.async_add_executor_job(_is_already_migrated, self.hass):
            return await self.async_step_already_migrated()
        return await self.async_step_confirm()

    async def async_step_already_migrated(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        # No explicit issue deletion needed - the repairs flow manager deletes it automatically
        # once any step returns async_create_entry.
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="already_migrated")

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="confirm")

        # Serialize the whole check-write-reload sequence against a second concurrent attempt
        # at this same flow (double submit, two admin sessions) - file writes below aren't
        # otherwise atomic, and HA's own per-entry setup_lock only protects a single entry's
        # setup/reload, not this flow's file I/O.
        async with _async_get_migration_lock(self.hass):
            # Validate before touching anything - if configuration.yaml is already broken,
            # stop rather than risk compounding an existing problem.
            baseline_error = await async_check_ha_config_file(self.hass)
            if baseline_error is not None:
                _LOGGER.warning("SUPERNOTIFY Migration aborted, configuration.yaml already invalid: %s", baseline_error)
                self._async_raise_manual_migration_issue("baseline_invalid")
                return self.async_show_form(step_id="confirm", errors={"base": "baseline_invalid"})

            # Validated here, on the event loop, rather than inside _write_files (which runs in
            # the executor): cv.template - used by cv.CONDITIONS_SCHEMA to coerce a bare Jinja
            # string condition (e.g. a scenario's `conditions: ["{{ ... }}"]` shorthand) - needs
            # the event-loop-bound hass context to do that; off the event loop it can't find it
            # and rejects an otherwise perfectly valid bare-string condition.
            migrated = _extract_yaml_only_config(self._legacy_config)
            try:
                SUPERNOTIFY_YAML_SCHEMA(migrated)
            except vol.Invalid as err:
                _LOGGER.warning("SUPERNOTIFY Legacy config failed validation, not migrating: %s", err)
                self._async_raise_manual_migration_issue("migrated_config_invalid")
                return self.async_show_form(step_id="confirm", errors={"base": "migrated_config_invalid"})

            write_error = await self.hass.async_add_executor_job(self._write_files, migrated)
            if write_error is not None:
                self._async_raise_manual_migration_issue(write_error)
                return self.async_show_form(step_id="confirm", errors={"base": write_error})

            # Validate again post-write - the baseline is known-good, so any failure here was
            # caused by our own edit and gets rolled back.
            after_error = await async_check_ha_config_file(self.hass)
            if after_error is not None:
                await self.hass.async_add_executor_job(self._rollback)
                _LOGGER.warning("SUPERNOTIFY Migration rolled back, configuration.yaml became invalid: %s", after_error)
                self._async_raise_manual_migration_issue("validation_failed")
                return self.async_show_form(step_id="confirm", errors={"base": "validation_failed"})

            ir.async_delete_issue(self.hass, DOMAIN, MANUAL_MIGRATION_ISSUE_ID)
            await self._async_finish_migration()
            return self.async_create_entry(data={})

    def _async_raise_manual_migration_issue(self, reason_key: str) -> None:
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            MANUAL_MIGRATION_ISSUE_ID,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=MANUAL_MIGRATION_ISSUE_ID,
            translation_placeholders={"reason": _MANUAL_MIGRATION_REASONS.get(reason_key, reason_key)},
        )

    def _write_files(self, migrated: dict[str, Any]) -> str | None:
        """Write supernotify.yaml and append the include line to configuration.yaml.

        `migrated` is already validated (see async_step_confirm - validation needs the event
        loop, this method doesn't have it). Blocking file I/O - runs in the executor. Returns
        an error-translation-key string on failure (nothing written), None on success
        (self._original_configuration_yaml is set, letting _rollback restore it if the
        post-write config-check fails).
        """
        supernotify_yaml_path = self.hass.config.path(SUPERNOTIFY_YAML_FILENAME)
        if os.path.exists(supernotify_yaml_path):
            return "supernotify_yaml_exists"

        configuration_yaml_path = self.hass.config.path(CONFIGURATION_YAML_FILENAME)
        try:
            with open(configuration_yaml_path, encoding="utf-8") as config_file:
                original_text = config_file.read()
        except OSError as err:
            _LOGGER.warning("SUPERNOTIFY Could not read %s: %s", configuration_yaml_path, err)
            return "configuration_yaml_unreadable"

        try:
            parsed = _load_configuration_yaml_dict(self.hass)
        except Exception:
            parsed = {}
        if DOMAIN in parsed:
            return "supernotify_key_exists"

        try:
            save_yaml(supernotify_yaml_path, migrated)
        except OSError as err:
            _LOGGER.warning("SUPERNOTIFY Could not write %s: %s", supernotify_yaml_path, err)
            return "write_failed"

        new_text = original_text if original_text.endswith("\n") else original_text + "\n"
        new_text += f"\n{DOMAIN}: !include {SUPERNOTIFY_YAML_FILENAME}\n"
        try:
            with open(configuration_yaml_path, "w", encoding="utf-8") as config_file:
                config_file.write(new_text)
        except OSError as err:
            _LOGGER.warning("SUPERNOTIFY Could not write %s: %s", configuration_yaml_path, err)
            os.remove(supernotify_yaml_path)
            return "write_failed"

        self._original_configuration_yaml = original_text
        return None

    def _rollback(self) -> None:
        supernotify_yaml_path = self.hass.config.path(SUPERNOTIFY_YAML_FILENAME)
        if os.path.exists(supernotify_yaml_path):
            os.remove(supernotify_yaml_path)
        if self._original_configuration_yaml is not None:
            configuration_yaml_path = self.hass.config.path(CONFIGURATION_YAML_FILENAME)
            with open(configuration_yaml_path, "w", encoding="utf-8") as config_file:
                config_file.write(self._original_configuration_yaml)

    async def _async_finish_migration(self) -> None:
        """Reload the migrated YAML immediately (no restart needed), and make sure an entry
        exists to own it - preserving a custom `name:` (-> notify.<name>) from the legacy
        config, since that's what determines the actual registered action name, along with any
        template_path/media_path/etc and archive/dupe_check/housekeeping settings the legacy
        config carried."""
        if not self.hass.config_entries.async_entries(DOMAIN):
            from homeassistant.config_entries import SOURCE_IMPORT

            await self.hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=self._legacy_config)
        else:
            async_sync_entry_from_legacy_config(self.hass, self._legacy_config)

        await async_reload_yaml_config_and_entries(self.hass)


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    """Create the repair flow for the legacy_yaml_config issue."""
    _ = hass, issue_id
    legacy_config_json = (data or {}).get("legacy_config")
    legacy_config = json.loads(legacy_config_json) if isinstance(legacy_config_json, str) else {}
    return SupernotifyLegacyYamlRepairFlow(legacy_config)
