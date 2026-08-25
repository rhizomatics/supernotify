from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_ENABLED
from homeassistant.data_entry_flow import FlowResultType

from custom_components.supernotify import DOMAIN, MEDIA_DIR, TEMPLATE_DIR
from custom_components.supernotify.const import (
    ATTR_DUPE_POLICY_MT,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
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
        menu_result["flow_id"], {CONF_ENABLED: True, CONF_ARCHIVE_DAYS: 5}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_ARCHIVE][CONF_ENABLED] is True
    assert entry.options[CONF_ARCHIVE][CONF_ARCHIVE_DAYS] == 5

    # re-opening the step is pre-filled with the values just saved
    options_init2 = await hass.config_entries.options.async_init(entry.entry_id)
    menu_result2 = await hass.config_entries.options.async_configure(options_init2["flow_id"], {"next_step_id": "archive"})
    assert menu_result2["data_schema"]({})[CONF_ARCHIVE_DAYS] == 5


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
