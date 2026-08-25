from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENABLED
from homeassistant.data_entry_flow import FlowResultType

from custom_components.supernotify import ATTR_IMPORTED_FROM_YAML, DOMAIN, MEDIA_DIR, TEMPLATE_DIR
from custom_components.supernotify.const import (
    ATTR_DUPE_POLICY_MT,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_EVENT_SELECTION,
    CONF_ARCHIVE_PATH,
    CONF_DELIVERY,
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
from custom_components.supernotify.schema import OutcomeSelection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_user_step_defaults_create_entry(hass: HomeAssistant) -> None:
    """Submitting the user step with no input reproduces minimal.yaml's zero-config defaults."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Supernotify"
    assert result2["data"] == {
        CONF_TEMPLATE_PATH: TEMPLATE_DIR,
        CONF_MEDIA_PATH: MEDIA_DIR,
        CONF_MEDIA_URL_PREFIX: "/supernotify/media",
        CONF_MOBILE_DISCOVERY: True,
        CONF_RECIPIENTS_DISCOVERY: True,
    }
    await hass.async_block_till_done()


async def test_single_instance_only(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    result2 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "single_instance_allowed"


async def test_reconfigure_updates_global_settings(hass: HomeAssistant, tmp_path: Path) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]

    reconfigure = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    assert reconfigure["type"] == FlowResultType.FORM
    assert reconfigure["step_id"] == "reconfigure"
    # pre-filled from the entry's current data
    assert reconfigure["data_schema"]({})[CONF_TEMPLATE_PATH] == TEMPLATE_DIR

    custom_template_path = str(tmp_path / "templates" / "custom")
    result2 = await hass.config_entries.flow.async_configure(
        reconfigure["flow_id"],
        {
            CONF_TEMPLATE_PATH: custom_template_path,
            CONF_MEDIA_PATH: MEDIA_DIR,
            CONF_MEDIA_URL_PREFIX: "/supernotify/media",
            CONF_MOBILE_DISCOVERY: False,
            CONF_RECIPIENTS_DISCOVERY: True,
        },
    )
    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert entry.data[CONF_TEMPLATE_PATH] == custom_template_path
    assert entry.data[CONF_MOBILE_DISCOVERY] is False


async def test_options_flow_menu(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry_id = entry_result["result"].entry_id

    options_result = await hass.config_entries.options.async_init(entry_id)
    assert options_result["type"] == FlowResultType.MENU
    assert options_result["menu_options"] == ["archive", "dupe_check", "housekeeping"]


async def test_options_flow_archive(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]

    options_init = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result = await hass.config_entries.options.async_configure(options_init["flow_id"], {"next_step_id": "archive"})
    assert menu_result["type"] == FlowResultType.FORM
    assert menu_result["step_id"] == "archive"

    result = await hass.config_entries.options.async_configure(
        menu_result["flow_id"],
        {
            CONF_ENABLED: True,
            "file": {CONF_ARCHIVE_DAYS: 5},
            "event": {
                CONF_ARCHIVE_EVENT_SELECTION: ["error", "dupe"],
                CONF_ARCHIVE_DIAGNOSTICS: [],
            },
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_ARCHIVE][CONF_ENABLED] is True
    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_DAYS] == 5
    # the ticked checkboxes are stored as the pipe-separated string parse_event_policy expects
    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_EVENT_SELECTION] == "ERROR|DUPE"
    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_DIAGNOSTICS] == "NONE"

    # re-opening the step is pre-filled with the values just saved, as a checkbox list again
    options_init2 = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result2 = await hass.config_entries.options.async_configure(options_init2["flow_id"], {"next_step_id": "archive"})
    prefilled = menu_result2["data_schema"]({})
    assert prefilled["file"][CONF_ARCHIVE_DAYS] == 5
    assert prefilled["event"][CONF_ARCHIVE_EVENT_SELECTION] == ["error", "dupe"]
    assert prefilled["event"][CONF_ARCHIVE_DIAGNOSTICS] == []


async def test_options_flow_dupe_check(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]

    options_init = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result = await hass.config_entries.options.async_configure(options_init["flow_id"], {"next_step_id": "dupe_check"})
    assert menu_result["step_id"] == "dupe_check"

    result = await hass.config_entries.options.async_configure(
        menu_result["flow_id"], {CONF_TTL: 30, CONF_SIZE: 10, CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_DUPE_CHECK][CONF_TTL] == 30
    assert entry.options[CONF_DUPE_CHECK][CONF_DUPE_POLICY] == ATTR_DUPE_POLICY_MT


async def test_options_flow_housekeeping(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]

    options_init = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result = await hass.config_entries.options.async_configure(options_init["flow_id"], {"next_step_id": "housekeeping"})
    assert menu_result["step_id"] == "housekeeping"

    result = await hass.config_entries.options.async_configure(
        menu_result["flow_id"], {CONF_HOUSEKEEPING_TIME: "01:02:03", CONF_MEDIA_STORAGE_DAYS: 14}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_HOUSEKEEPING][CONF_HOUSEKEEPING_TIME] == "01:02:03"
    assert entry.options[CONF_HOUSEKEEPING][CONF_MEDIA_STORAGE_DAYS] == 14


async def test_import_mirrors_yaml_config(hass: HomeAssistant) -> None:
    import_data = {
        CONF_TEMPLATE_PATH: "/config/templates/supernotify",
        CONF_MEDIA_PATH: "supernotify/media",
        CONF_MEDIA_URL_PREFIX: "/supernotify/media",
        CONF_MOBILE_DISCOVERY: True,
        CONF_RECIPIENTS_DISCOVERY: False,
        CONF_ARCHIVE: {CONF_ENABLED: True, CONF_ARCHIVE_PATH: "/config/archive/supernotify", CONF_ARCHIVE_DAYS: 5},
        CONF_DUPE_CHECK: {CONF_TTL: 30},
        CONF_HOUSEKEEPING: {CONF_HOUSEKEEPING_TIME: "00:00:01"},
        CONF_DELIVERY: {"some_delivery": {}},
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data=import_data)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Supernotify (imported from YAML)"
    entry = result["result"]

    assert entry.data[CONF_TEMPLATE_PATH] == "/config/templates/supernotify"
    assert entry.data[CONF_RECIPIENTS_DISCOVERY] is False
    assert CONF_ARCHIVE_PATH not in entry.data
    assert entry.data[ATTR_IMPORTED_FROM_YAML] is True

    # archive_path lives in the mirrored archive options, alongside the rest of archive
    assert entry.options[CONF_ARCHIVE] == {
        CONF_ENABLED: True,
        CONF_ARCHIVE_PATH: "/config/archive/supernotify",
        CONF_ARCHIVE_DAYS: 5,
    }
    assert entry.options[CONF_DUPE_CHECK] == {CONF_TTL: 30}
    assert entry.options[CONF_HOUSEKEEPING] == {CONF_HOUSEKEEPING_TIME: "00:00:01"}
    # deliveries/transports/scenarios etc are not mirrored - YAML-only for this phase
    assert CONF_DELIVERY not in entry.data
    assert CONF_DELIVERY not in entry.options


async def test_import_normalizes_event_selection_and_time(hass: HomeAssistant) -> None:
    """Regression test: a YAML-imported archive config carries real OutcomeSelection/time
    objects (already coerced by SUPERNOTIFY_SCHEMA), which must be stored as the plain
    "NAME|NAME" strings and ISO time string the options form expects - not the raw
    IntFlag/datetime.time values, which would render as a bare, meaningless number in the UI."""
    import_data = {
        CONF_ARCHIVE: {
            CONF_ENABLED: True,
            CONF_ARCHIVE_EVENT_SELECTION: OutcomeSelection.NO_DELIVERY | OutcomeSelection.ERROR,
            CONF_ARCHIVE_DIAGNOSTICS: OutcomeSelection.ERROR,
        },
        CONF_HOUSEKEEPING: {CONF_HOUSEKEEPING_TIME: dt.time(0, 0, 1)},
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data=import_data)
    entry = result["result"]

    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_EVENT_SELECTION] == "NO_DELIVERY|ERROR"
    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_DIAGNOSTICS] == "ERROR"
    assert entry.options[CONF_HOUSEKEEPING][CONF_HOUSEKEEPING_TIME] == "00:00:01"


async def test_archive_options_form_normalizes_stale_raw_values(hass: HomeAssistant) -> None:
    """Defensive path: an entry already holding raw int/time values (e.g. imported before
    the fix above existed) must still render sensible text in the options form, not numbers."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ARCHIVE: {CONF_ARCHIVE_EVENT_SELECTION: 30, CONF_ARCHIVE_DIAGNOSTICS: 16},
            CONF_HOUSEKEEPING: {CONF_HOUSEKEEPING_TIME: dt.time(1, 2, 3)},
        },
    )

    options_init = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result = await hass.config_entries.options.async_configure(options_init["flow_id"], {"next_step_id": "archive"})
    prefilled = menu_result["data_schema"]({})
    assert prefilled["event"][CONF_ARCHIVE_EVENT_SELECTION] == ["no_delivery", "partial_delivery", "fallback_delivery", "error"]
    assert prefilled["event"][CONF_ARCHIVE_DIAGNOSTICS] == ["error"]

    options_init2 = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result2 = await hass.config_entries.options.async_configure(options_init2["flow_id"], {"next_step_id": "housekeeping"})
    prefilled2 = menu_result2["data_schema"]({})
    assert prefilled2[CONF_HOUSEKEEPING_TIME] == "01:02:03"


async def test_import_without_archive_path(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data={})
    entry = result["result"]
    assert CONF_ARCHIVE_PATH not in entry.data
    assert CONF_ARCHIVE not in entry.options


async def test_import_declines_second_entry(hass: HomeAssistant) -> None:
    first = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data={})
    await hass.async_block_till_done()
    assert first["type"] == FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "import"}, data={})
    assert second["type"] == FlowResultType.ABORT
    assert second["reason"] == "single_instance_allowed"


async def test_user_step_creates_missing_template_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """A template_path that doesn't exist yet is created on submit, not rejected - matching
    media_path's own tolerant behavior."""
    new_template_path = tmp_path / "templates" / "subdir"
    assert not new_template_path.exists()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TEMPLATE_PATH: str(new_template_path)})

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert new_template_path.exists()


async def test_user_step_rejects_unusable_template_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """A template_path that can never be created (blocked by a plain file in the way) is a
    form error, not silently accepted."""
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("")
    unusable_path = str(blocking_file / "templates")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_TEMPLATE_PATH: unusable_path})

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_TEMPLATE_PATH: "template_path_invalid"}


async def test_user_step_creates_missing_media_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """A media_path that doesn't exist yet is created on submit, not rejected - matching
    MediaStorage.initialize()'s own tolerant runtime behavior (media_grab.py)."""
    new_media_path = tmp_path / "media" / "subdir"
    assert not new_media_path.exists()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MEDIA_PATH: str(new_media_path)})

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert new_media_path.exists()


async def test_user_step_rejects_unusable_media_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """A media_path that can never be created (blocked by a plain file in the way) is a form
    error, not silently accepted."""
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("")
    unusable_path = str(blocking_file / "media")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_MEDIA_PATH: unusable_path})

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_MEDIA_PATH: "media_path_invalid"}


async def test_reconfigure_step_rejects_unusable_media_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """The reconfigure step validates the same way as the user step, re-showing the
    just-submitted (invalid) values rather than reverting to the entry's prior data."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    entry_result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    entry = entry_result["result"]

    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("")
    unusable_path = str(blocking_file / "media")

    reconfigure = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
    )
    result2 = await hass.config_entries.flow.async_configure(
        reconfigure["flow_id"],
        {
            CONF_TEMPLATE_PATH: TEMPLATE_DIR,
            CONF_MEDIA_PATH: unusable_path,
            CONF_MEDIA_URL_PREFIX: "/supernotify/media",
            CONF_MOBILE_DISCOVERY: True,
            CONF_RECIPIENTS_DISCOVERY: True,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "reconfigure"
    assert result2["errors"] == {CONF_MEDIA_PATH: "media_path_invalid"}
    # entry untouched - the invalid submission was never applied
    assert entry.data[CONF_MEDIA_PATH] == MEDIA_DIR
