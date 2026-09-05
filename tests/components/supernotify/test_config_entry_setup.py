from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import CONF_MEDIA_PATH
from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_setup_entry_registers_notify_service(hass: HomeAssistant) -> None:
    """A zero-input config entry reproduces minimal.yaml end to end: notify.supernotify works."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "supernotify")

    await hass.services.async_call("notify", "supernotify", {"message": "hello there", "title": "testing"}, blocking=True)
    await hass.async_block_till_done()

    # no recipients/target configured (a truly empty, minimal.yaml-equivalent setup), so
    # there's nowhere to route the message - the point here is that the call reaches a live
    # SupernotifyAction wired up by the config entry, without raising
    assert entry.runtime_data is not None
    assert entry.runtime_data.failures == 0


async def test_setup_entry_uses_archive_path_from_options(hass: HomeAssistant) -> None:
    """archive_path lives in the archive options section, matching FULL_CONFIG_SCHEMA's
    nested shape directly - no folding needed between entry.data and entry.options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"archive": {"file_path": "/config/supernotify_archive"}})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data is not None
    assert entry.runtime_data.context.archive.configured_archive_path == "/config/supernotify_archive"


async def test_unload_entry_removes_notify_service(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service("notify", "supernotify")


async def test_setup_entry_registers_supplemental_services(hass: HomeAssistant) -> None:
    """Config-entry setup exposes the same supernotify.* debug/admin services regardless of
    whether any YAML config exists."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "enquire_configuration")
    assert hass.services.has_service(DOMAIN, "enquire_scenarios")
    assert hass.services.has_service(DOMAIN, "purge_media")


async def test_purge_archive_raises_when_archive_not_configured(hass: HomeAssistant) -> None:
    """A zero-config entry (minimal.yaml-equivalent) has no archive configured - calling
    purge_archive should raise a ServiceValidationError, not silently return an error dict
    a caller might not check."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="No archive configured"):
        await hass.services.async_call(DOMAIN, "purge_archive", blocking=True, return_response=True)


async def test_purge_media_raises_when_media_not_configured(hass: HomeAssistant) -> None:
    """An entry with media_path explicitly cleared has no media storage configured -
    calling purge_media should raise a ServiceValidationError."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_MEDIA_PATH: ""}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="No media storage configured"):
        await hass.services.async_call(DOMAIN, "purge_media", blocking=True, return_response=True)


async def test_unload_entry_removes_supplemental_services(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "enquire_configuration")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "enquire_configuration")


async def test_options_update_reloads_entry_with_new_archive_path(hass: HomeAssistant) -> None:
    """Archive/dupe_check/housekeeping options must take effect without a manual reload or HA
    restart - the options flow's async_create_entry only updates entry.options, so an update
    listener has to reload the entry itself for the new values to reach the running service."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"archive": {"file_path": "/config/archive_v1"}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.context.archive.configured_archive_path == "/config/archive_v1"

    hass.config_entries.async_update_entry(entry, options={"archive": {"file_path": "/config/archive_v2"}})
    await hass.async_block_till_done()

    assert entry.runtime_data.context.archive.configured_archive_path == "/config/archive_v2"


async def test_setup_entry_raises_config_entry_not_ready_on_initialize_failure(hass: HomeAssistant) -> None:
    """A failure during SupernotifyAction.initialize() should leave HA free to retry setup
    (ConfigEntryState.SETUP_RETRY), not propagate as a raw unhandled exception."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.supernotify.notify.SupernotifyAction.initialize",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_registers_notify_action(hass: HomeAssistant) -> None:
    """supernotify.notify is a schema-typed alternative to notify.supernotify, with fields
    (priority, delivery, scenarios, etc) promoted out of the generic `data:` blob - registered
    alongside the other supplemental domain-scoped services."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "notify")

    await hass.services.async_call(
        DOMAIN, "notify", {"message": "hello there", "title": "testing", "priority": "high"}, blocking=True
    )
    await hass.async_block_till_done()

    assert entry.runtime_data is not None
    assert entry.runtime_data.failures == 0
    assert entry.runtime_data.last_notification is not None
    assert entry.runtime_data.last_notification.priority == "high"


async def test_notify_action_rejects_invalid_field() -> None:
    """A rich, schema-checked field (priority) should reject values outside the known set,
    same as it would nested under notify.supernotify's `data:` blob."""
    with pytest.raises(vol.Invalid):
        NOTIFY_ACTION_SCHEMA({"message": "hello", "priority": ["not", "a", "priority"]})


async def test_notify_action_propagates_calling_context(hass: HomeAssistant) -> None:
    """Unlike notify.supernotify - routed through HA's legacy notify platform, which drops the
    calling Context (see the 2.3.0 changelog note on this limitation) - supernotify.notify is
    called directly and must forward the Context through to the resulting Notification."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    call_context = Context()
    await hass.services.async_call(DOMAIN, "notify", {"message": "hello there"}, blocking=True, context=call_context)
    await hass.async_block_till_done()

    assert entry.runtime_data.last_notification is not None
    assert entry.runtime_data.last_notification.ha_context is call_context


async def test_notify_action_promotes_media_fields_into_media_block(hass: HomeAssistant) -> None:
    """camera_entity_id/snapshot_url/clip_url are top-level fields only on supernotify.notify
    (for their own selectors in the action UI), but Notification only understands them nested
    under media: - supplemental_action_notify must fold them in before dispatch."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set("camera.front_door", "idle")
    await hass.services.async_call(
        DOMAIN,
        "notify",
        {
            "message": "hello there",
            "camera_entity_id": "camera.front_door",
            "snapshot_url": "http://example.com/snap.jpg",
            "clip_url": "http://example.com/clip.mp4",
            "media": {"camera_delay": 3},
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.last_notification is not None
    assert entry.runtime_data.last_notification.media == {
        "camera_entity_id": "camera.front_door",
        "snapshot_url": "http://example.com/snap.jpg",
        "clip_url": "http://example.com/clip.mp4",
        "camera_delay": 3,
    }


async def test_notify_action_top_level_media_field_overrides_nested_media_block(hass: HomeAssistant) -> None:
    """If camera_entity_id is set both as a top-level field and nested inside media: on
    supernotify.notify, the nested value is ignored - the top-level field is the one with a
    dedicated selector in the action UI, so it wins."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {
            "message": "hello there",
            "camera_entity_id": "camera.front_door",
            "media": {"camera_entity_id": "camera.back_door", "camera_delay": 3},
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert entry.runtime_data.last_notification is not None
    assert entry.runtime_data.last_notification.media == {"camera_entity_id": "camera.front_door", "camera_delay": 3}


async def test_unload_entry_removes_notify_action(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "notify")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "notify")
