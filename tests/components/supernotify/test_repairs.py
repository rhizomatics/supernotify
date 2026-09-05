from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import yaml
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.notify import async_get_service
from custom_components.supernotify.repairs import (
    ISSUE_ID,
    MANUAL_MIGRATION_ISSUE_ID,
    SupernotifyLegacyYamlRepairFlow,
    async_create_fix_flow,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant

LEGACY_CONFIG = {
    "name": "supernotify",
    "platform": "supernotify",
    "delivery": {"push": {"transport": "mobile_push"}},
    "recipients": [{"person": "person.house_owner"}],
}


def _flow(hass: HomeAssistant, legacy_config: dict | None = None) -> SupernotifyLegacyYamlRepairFlow:
    flow = SupernotifyLegacyYamlRepairFlow(legacy_config if legacy_config is not None else dict(LEGACY_CONFIG))
    flow.hass = hass
    return flow


async def test_shim_creates_fixable_issue_and_registers_nothing(hass: HomeAssistant) -> None:
    """A leftover legacy `notify: - platform: supernotify` block is inert - the shim raises
    the fixable repair and declines to build a service (returns None)."""
    service = await async_get_service(hass, dict(LEGACY_CONFIG))
    assert service is None

    issue_registry = ir.async_get(hass)
    issue = issue_registry.async_get_issue(DOMAIN, ISSUE_ID)
    assert issue is not None
    assert issue.is_fixable


async def test_shim_backfills_name_on_pre_existing_entry_without_waiting_for_repair(hass: HomeAssistant) -> None:
    """Regression test: an entry mirrored by a pre-this-session version never had `name` in
    entry.data at all (that field didn't exist yet). Once the config entry became the sole
    owner of the service, such an entry would silently register notify.supernotify instead of
    the real notify.supernotifier from `name: SuperNotifier` in the still-present legacy YAML -
    breaking every automation calling the old action, and only fixable by actually opening and
    submitting the migration repair. The name has to sync automatically on every load instead."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")

    legacy_config = {**LEGACY_CONFIG, "name": "SuperNotifier"}
    service = await async_get_service(hass, legacy_config)
    assert service is None
    await hass.async_block_till_done()

    assert entry.data["name"] == "SuperNotifier"
    assert hass.services.has_service("notify", "supernotifier")
    assert not hass.services.has_service("notify", "supernotify")


async def test_shim_backfills_archive_options_on_pre_existing_entry_without_waiting_for_repair(
    hass: HomeAssistant,
) -> None:
    """Regression test: on a clean start, async_setup already auto-bootstraps a blank config
    entry (options={}) before anyone gets around to opening and confirming the migration
    repair. Until this was fixed, only `name` was synced onto that entry on every load - the
    archive/dupe_check/housekeeping settings stayed blank (archive disabled, no path) on every
    restart until the repair was manually confirmed, silently losing them just like the
    already-fixed name-backfill case above."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_config = {
        **LEGACY_CONFIG,
        "archive": {"enabled": True, "file_path": "/config/archive/supernotify", "file_retention_days": 3},
        "dupe_check": {"ttl": 120},
    }
    service = await async_get_service(hass, legacy_config)
    assert service is None
    await hass.async_block_till_done()

    assert entry.options["archive"]["enabled"] is True
    assert entry.options["archive"]["file_path"] == "/config/archive/supernotify"
    assert entry.options["dupe_check"]["ttl"] == 120


async def test_shim_backfills_data_fields_on_pre_existing_entry_without_waiting_for_repair(hass: HomeAssistant) -> None:
    """Regression test: template_path/media_path/media_url_prefix/mobile_discovery/
    recipients_discovery from the legacy block were never synced onto a pre-existing entry at
    all - only `name` and (after the previous fix) archive/dupe_check/housekeeping were. A
    customized template_path/media_path would silently stay at the auto-bootstrapped defaults
    forever unless the user manually re-entered them via Reconfigure."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_config = {
        **LEGACY_CONFIG,
        "template_path": "/config/templates/supernotify",
        "media_path": "/config/media/supernotify",
    }
    service = await async_get_service(hass, legacy_config)
    assert service is None
    await hass.async_block_till_done()

    assert entry.data["template_path"] == "/config/templates/supernotify"
    assert entry.data["media_path"] == "/config/media/supernotify"


async def test_shim_migrates_minimal_config_without_any_repair(hass: HomeAssistant) -> None:
    """A 'simple' legacy config - no delivery, transports, scenarios, recipients, cameras,
    action_groups, links, snooze, nothing that needs moving into supernotify.yaml - must be fully
    migrated (name, paths, archive) just by loading, with no need to ever open or confirm the
    migration repair: per the README, "If you have an existing simple configuration, everything
    will be migrated for you and there will be no YAML needed."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    minimal_legacy_config = {
        "name": "SuperNotifier",
        "platform": "supernotify",
        "template_path": "/config/templates/supernotify",
        "media_path": "/config/media/supernotify",
        "archive": {"enabled": True, "file_path": "/config/archive/supernotify"},
    }
    service = await async_get_service(hass, minimal_legacy_config)
    assert service is None
    await hass.async_block_till_done()

    assert entry.data["name"] == "SuperNotifier"
    assert entry.data["template_path"] == "/config/templates/supernotify"
    assert entry.data["media_path"] == "/config/media/supernotify"
    assert entry.options["archive"]["enabled"] is True
    assert entry.options["archive"]["file_path"] == "/config/archive/supernotify"
    assert hass.services.has_service("notify", "supernotifier")


async def test_shim_sync_reaches_the_live_running_service_not_just_stored_config(hass: HomeAssistant, tmp_path: Path) -> None:
    """Regression test: entry.data/entry.options getting the right values (what the other
    shim-backfill tests above check, and what the Reconfigure screen reads) is not the same as
    the *running* service actually using them. A pre-existing entry starts out on defaults, so
    the shim's sync is really several fields (name, template_path, archive.enabled, ...) all
    changing at once - and calling async_update_entry more than once in that single sync used to
    race: Python's eager task execution can start the first update's reload (which unloads the
    entry, removing its update listener) before the second update call runs, so the second
    update's "notify listeners to reload" step finds no listener and silently no-ops. The entry
    ends up stuck running the FIRST update's (still-blank) config forever, even though
    entry.data/entry.options themselves end up fully correct - exactly the reported symptom
    (Reconfigure showed the right template_path, but the live service still logged the default
    "supernotify/templates" not found, and archive stayed disabled)."""
    template_dir = tmp_path / "templates" / "supernotify"
    template_dir.mkdir(parents=True)

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    legacy_config = {
        **LEGACY_CONFIG,
        "template_path": str(template_dir),
        "archive": {"enabled": True, "file_path": "/config/archive/supernotify"},
    }
    service = await async_get_service(hass, legacy_config)
    assert service is None
    await hass.async_block_till_done()

    # stored config: already covered above, re-asserted here for context
    assert entry.data["template_path"] == str(template_dir)
    assert entry.options["archive"]["enabled"] is True

    # the live running service must reflect the same values, not just entry.data/entry.options
    assert str(entry.runtime_data.context.custom_template_path) == str(template_dir)
    assert entry.runtime_data.context.archive.enabled is True


async def test_fix_flow_happy_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """Confirming the fix writes supernotify.yaml, appends the include line to
    configuration.yaml, and the migrated config is live without a restart."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    flow = _flow(hass)
    form = await flow.async_step_init()
    assert form["type"] == FlowResultType.FORM
    assert form["step_id"] == "confirm"

    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    supernotify_yaml = tmp_path / "supernotify.yaml"
    assert supernotify_yaml.exists()
    written = yaml.safe_load(supernotify_yaml.read_text())
    assert written["delivery"]["push"]["transport"] == "mobile_push"
    # ConfigEntry-owned keys (archive/etc) and platform/name must not leak into supernotify.yaml
    assert "platform" not in written
    assert "name" not in written

    configuration_yaml_text = (tmp_path / "configuration.yaml").read_text()
    assert "supernotify: !include supernotify.yaml" in configuration_yaml_text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert hass.services.has_service("notify", "supernotify")

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, MANUAL_MIGRATION_ISSUE_ID) is None


async def test_fix_flow_accepts_bare_string_template_condition(hass: HomeAssistant, tmp_path: Path) -> None:
    """Regression test: a scenario's `conditions:` list may contain a bare Jinja string as
    shorthand for a template condition (cv.CONDITIONS_SCHEMA coerces it via cv.template) - that
    coercion needs the event-loop-bound hass context, so validating it from the executor thread
    (as _write_files used to) rejected perfectly valid config with "Expected a dictionary"."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    legacy_config = {
        **LEGACY_CONFIG,
        "scenarios": {
            "xmas": {
                "alias": "Christmas season",
                "conditions": {
                    "condition": "or",
                    "conditions": [
                        "{{ (12,1) <= (now().month, now().day) <= (12,31) }}",
                        "{{ (1,1) <= (now().month, now().day) <= (1,7) }}",
                    ],
                },
            }
        },
    }
    flow = _flow(hass, legacy_config)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    written = yaml.safe_load((tmp_path / "supernotify.yaml").read_text())
    assert written["scenarios"]["xmas"]["conditions"]["conditions"][0] == "{{ (12,1) <= (now().month, now().day) <= (12,31) }}"


async def test_fix_flow_preserves_custom_name(hass: HomeAssistant, tmp_path: Path) -> None:
    """A legacy `name:` (-> notify.<name>) is carried onto the bootstrapped entry, since that's
    what determines the actual registered action once the entry owns it exclusively."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    legacy_config = {**LEGACY_CONFIG, "name": "SuperNotifier"}
    flow = _flow(hass, legacy_config)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data["name"] == "SuperNotifier"
    assert hass.services.has_service("notify", "supernotifier")


async def test_fix_flow_refuses_when_supernotify_yaml_exists(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")
    (tmp_path / "supernotify.yaml").write_text("delivery: {}\n")

    flow = _flow(hass)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "supernotify_yaml_exists"}

    # nothing else was touched
    assert (tmp_path / "configuration.yaml").read_text() == "homeassistant:\n"

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, MANUAL_MIGRATION_ISSUE_ID) is not None


async def test_fix_flow_refuses_when_supernotify_key_exists(hass: HomeAssistant, tmp_path: Path) -> None:
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\nsupernotify:\n  delivery: {}\n")

    flow = _flow(hass)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "supernotify_key_exists"}
    assert not (tmp_path / "supernotify.yaml").exists()


async def test_fix_flow_stops_when_baseline_config_already_invalid(hass: HomeAssistant, tmp_path: Path) -> None:
    """If configuration.yaml already has an unrelated problem, the migration must not attempt
    to write anything - and should raise the dedicated manual-migration issue."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n  this_is_not_a_valid_key: [\n")

    flow = _flow(hass)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "baseline_invalid"}
    assert not (tmp_path / "supernotify.yaml").exists()

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, MANUAL_MIGRATION_ISSUE_ID) is not None


async def test_fix_flow_stops_when_migrated_config_is_invalid(hass: HomeAssistant, tmp_path: Path) -> None:
    """If the extracted supernotify: content itself fails schema validation (a bad legacy
    config), nothing gets written - checked directly against SUPERNOTIFY_YAML_SCHEMA, since
    async_check_ha_config_file only treats schema failures as blocking for frontend-critical
    domains and would otherwise let a broken supernotify: config through as a mere warning."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    invalid_legacy_config = {**LEGACY_CONFIG, "delivery": {"push": {"transport": "not_a_real_transport"}}}
    flow = _flow(hass, invalid_legacy_config)
    await flow.async_step_init()
    result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "migrated_config_invalid"}

    assert not (tmp_path / "supernotify.yaml").exists()
    assert (tmp_path / "configuration.yaml").read_text() == "homeassistant:\n"

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, MANUAL_MIGRATION_ISSUE_ID) is not None


async def test_concurrent_confirm_attempts_do_not_interleave(hass: HomeAssistant, tmp_path: Path) -> None:
    """Two concurrent submits of the confirm step (double submit, two admin sessions) must not
    race on the file writes - the migration lock serializes them, so exactly one succeeds and
    the other cleanly sees the first one's already-written supernotify.yaml."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    flow_a = _flow(hass)
    flow_b = _flow(hass)
    await flow_a.async_step_init()
    await flow_b.async_step_init()

    result_a, result_b = await asyncio.gather(
        flow_a.async_step_confirm({}),
        flow_b.async_step_confirm({}),
    )
    results = [result_a, result_b]
    successes = [r for r in results if r["type"] == FlowResultType.CREATE_ENTRY]
    failures = [r for r in results if r["type"] == FlowResultType.FORM]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0]["errors"] == {"base": "supernotify_yaml_exists"}


async def test_already_migrated_check_tolerates_unparsable_configuration_yaml(hass: HomeAssistant, tmp_path: Path) -> None:
    """A supernotify.yaml existing alongside an unparsable configuration.yaml can't confirm
    the include is actually there - treated as not-yet-migrated rather than raising."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("this: is: not: valid: yaml: [\n")
    (tmp_path / "supernotify.yaml").write_text("delivery: {}\n")

    flow = _flow(hass)
    form = await flow.async_step_init()
    assert form["step_id"] == "confirm"


async def test_fix_flow_rolls_back_on_post_write_validation_failure(hass: HomeAssistant, tmp_path: Path) -> None:
    """If configuration.yaml somehow fails HA's own overall validation only after our edit
    (not caught by the pre-write SUPERNOTIFY_YAML_SCHEMA check, e.g. a problem in an unrelated
    section our append happens to break), the write is rolled back rather than left broken."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    flow = _flow(hass)
    await flow.async_step_init()
    with patch(
        "custom_components.supernotify.repairs.async_check_ha_config_file",
        AsyncMock(side_effect=[None, "boom"]),
    ):
        result = await flow.async_step_confirm({})
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "validation_failed"}

    assert not (tmp_path / "supernotify.yaml").exists()
    assert (tmp_path / "configuration.yaml").read_text() == "homeassistant:\n"

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, MANUAL_MIGRATION_ISSUE_ID) is not None


async def test_already_migrated_step_only_dismisses_issue(hass: HomeAssistant, tmp_path: Path) -> None:
    """If supernotify.yaml and the include already exist (a prior run, or hand migration), the
    flow should not attempt to write anything again - just offer to dismiss the nag."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\nsupernotify: !include supernotify.yaml\n")
    (tmp_path / "supernotify.yaml").write_text("delivery: {}\n")

    flow = _flow(hass)
    form = await flow.async_step_init()
    assert form["step_id"] == "already_migrated"

    result = await flow.async_step_already_migrated({})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    # nothing written/changed
    assert (tmp_path / "supernotify.yaml").read_text() == "delivery: {}\n"


async def test_already_migrated_check_handles_secrets_in_configuration_yaml(hass: HomeAssistant, tmp_path: Path) -> None:
    """Regression test: a real configuration.yaml with a `!secret` reference anywhere in it
    (extremely common) must still be recognized as already-migrated - without a Secrets object,
    load_yaml_dict raises on any `!secret` tag, which was previously swallowed by a broad except
    and misread as "not migrated", making the repair reappear on every restart even after a
    successful migration."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "secrets.yaml").write_text("api_key: hunter2\n")
    (tmp_path / "configuration.yaml").write_text(
        "homeassistant:\nsupernotify: !include supernotify.yaml\nsome_other_integration:\n  api_key: !secret api_key\n"
    )
    (tmp_path / "supernotify.yaml").write_text("delivery: {}\n")

    flow = _flow(hass)
    form = await flow.async_step_init()
    assert form["step_id"] == "already_migrated"


async def test_async_create_fix_flow_decodes_legacy_config(hass: HomeAssistant) -> None:
    """The repairs framework's entry point (async_create_fix_flow) decodes the JSON-encoded
    legacy_config issue data back into the dict the flow works with."""
    legacy_json = json.dumps({"delivery": {"push": {"transport": "mobile_push"}}})
    flow = await async_create_fix_flow(hass, ISSUE_ID, {"legacy_config": legacy_json})
    assert isinstance(flow, SupernotifyLegacyYamlRepairFlow)
    assert flow._legacy_config["delivery"]["push"]["transport"] == "mobile_push"


async def test_fix_flow_updates_existing_entry_name(hass: HomeAssistant, tmp_path: Path) -> None:
    """A pre-existing entry (from a UI-only or previously-migrated install) gets its `name`
    updated to match the legacy config's, if different - so the migration doesn't silently
    change which notify.<name> action ends up being the live one."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.data["name"] == DOMAIN

    legacy_config = {**LEGACY_CONFIG, "name": "SuperNotifier"}
    flow = _flow(hass, legacy_config)
    await flow.async_step_init()
    result2 = await flow.async_step_confirm({})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.data["name"] == "SuperNotifier"


async def test_fix_flow_merges_archive_options_onto_existing_entry(hass: HomeAssistant, tmp_path: Path) -> None:
    """Regression test: async_setup already auto-bootstraps a blank config entry (options={})
    before the interactive repair ever runs, so this always hits the pre-existing-entry branch
    in practice, not the fresh-entry async_step_import path. That branch used to only sync
    `name`, silently dropping archive/dupe_check/housekeeping (e.g. archive.enabled and
    archive.file_path) from the legacy YAML config."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.options == {}

    legacy_config = {
        **LEGACY_CONFIG,
        "archive": {"enabled": True, "file_path": "/config/supernotify_archive"},
        "dupe_check": {"ttl": 120},
    }
    flow = _flow(hass, legacy_config)
    await flow.async_step_init()
    result2 = await flow.async_step_confirm({})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options["archive"]["enabled"] is True
    assert entry.options["archive"]["file_path"] == "/config/supernotify_archive"
    assert entry.options["dupe_check"]["ttl"] == 120
