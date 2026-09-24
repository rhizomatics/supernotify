from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.actions import lift_legacy_nested_data
from custom_components.supernotify.const import CONF_MEDIA_PATH
from custom_components.supernotify.model import Target
from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA

if TYPE_CHECKING:
    from pathlib import Path

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
    # SuperNotificationService wired up by the config entry, without raising
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


async def test_setup_entry_registers_engine_actions(hass: HomeAssistant) -> None:
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


async def test_purge_media_removes_old_files(hass: HomeAssistant, tmp_path: Path) -> None:
    """purge_media deletes files older than the configured days by default, and honours a
    per-call days override, reporting what was purged and what remains."""
    old_file = tmp_path / "old.jpg"
    mid_file = tmp_path / "mid.jpg"
    new_file = tmp_path / "new.jpg"
    now = time.time()
    for file, age_days in ((old_file, 10), (mid_file, 3), (new_file, 0)):
        file.write_bytes(b"x")
        os.utime(file, (now - age_days * 86400, now - age_days * 86400))

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_MEDIA_PATH: str(tmp_path)}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    media_storage = entry.runtime_data.context.media_storage
    interval = media_storage.purge_minute_interval

    response = await hass.services.async_call(DOMAIN, "purge_media", blocking=True, return_response=True)
    assert response == {"purged": 1, "remaining": 2, "interval": interval, "days": media_storage.days}
    assert not old_file.exists()
    assert mid_file.exists()
    assert new_file.exists()

    response = await hass.services.async_call(DOMAIN, "purge_media", {"days": 2}, blocking=True, return_response=True)
    assert response == {"purged": 1, "remaining": 1, "interval": interval, "days": 2}
    assert not mid_file.exists()
    assert new_file.exists()


async def test_unload_entry_removes_engine_actions(hass: HomeAssistant) -> None:
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
    """A failure during SuperNotificationService.initialize() should leave HA free to retry setup
    (ConfigEntryState.SETUP_RETRY), not propagate as a raw unhandled exception."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    with patch(
        "custom_components.supernotify.engine.SupernotifyEngine.initialize",
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
    under media: - action_notify must fold them in before dispatch."""
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


async def test_notify_action_merges_custom_target_into_dict_target(hass: HomeAssistant) -> None:
    """custom_target is a free-text escape hatch for identifiers the target: selector can't
    produce - e-mail addresses, phone numbers, Slack ids etc. action_notify must
    merge it into target before Notification ever sees it, classifying recognisable identifiers
    (e-mail, phone) same as if they'd been typed into a flat target list, and leaving anything
    unrecognised (e.g. a Slack id) as an opaque custom target."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {
            "message": "hello there",
            "target": {"entity_id": ["switch.hall"]},
            "custom_target": ["joe@example.com", "+4497177848484", "U123SLACK"],
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    target = entry.runtime_data.last_notification._target
    assert target is not None
    assert target.entity_ids == ["switch.hall"]
    assert target.email == ["joe@example.com"]
    assert target.phone == ["+4497177848484"]
    assert target.targets.get(Target.UNKNOWN_CUSTOM_CATEGORY) == ["U123SLACK"]


async def test_notify_action_custom_target_alone_populates_target(hass: HomeAssistant) -> None:
    """custom_target must still work with no target: selector value at all."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"message": "hello there", "custom_target": "joe@example.com"},
        blocking=True,
    )
    await hass.async_block_till_done()

    target = entry.runtime_data.last_notification._target
    assert target is not None
    assert target.email == ["joe@example.com"]


async def test_unload_entry_removes_notify_action(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(DOMAIN, "notify")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "notify")


async def test_disable_then_enable_entry_rewires_notify_service(hass: HomeAssistant) -> None:
    """Disabling from the UI unloads the entry same as any other unload (async_set_disabled_by
    -> async_reload -> async_unload_entry), then re-enabling sets it up again. Both
    notify.supernotify and the supernotify.* supplemental services must track that cycle -
    not be left stale from before the disable, nor missing after the re-enable."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")
    assert hass.services.has_service(DOMAIN, "enquire_configuration")

    await hass.config_entries.async_set_disabled_by(entry.entry_id, ConfigEntryDisabler.USER)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service("notify", "supernotify")
    assert not hass.services.has_service(DOMAIN, "enquire_configuration")

    await hass.config_entries.async_set_disabled_by(entry.entry_id, None)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service("notify", "supernotify")
    assert hass.services.has_service(DOMAIN, "enquire_configuration")

    # confirm notify.supernotify now reaches the freshly re-enabled engine, not a stale one
    await hass.services.async_call("notify", "supernotify", {"message": "post re-enable check"}, blocking=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.last_notification is not None
    assert entry.runtime_data.last_notification.message == "post re-enable check"


async def test_remove_then_readd_entry_recreates_notify_service(hass: HomeAssistant) -> None:
    """Removing the integration from the UI unloads then deletes the entry. Re-adding it (a
    fresh entry, since single_config_entry only blocks a second *simultaneous* entry) must not
    be blocked by anything left behind by the removed one - notably notify.supernotify, which
    a prior bug left registered forever once created, permanently blocking re-registration."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service("notify", "supernotify")
    assert not hass.services.has_service(DOMAIN, "enquire_configuration")

    new_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    new_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(new_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")

    await hass.services.async_call("notify", "supernotify", {"message": "post re-add check"}, blocking=True)
    await hass.async_block_till_done()
    assert new_entry.runtime_data.last_notification is not None
    assert new_entry.runtime_data.last_notification.message == "post re-add check"


async def test_ha_shutdown_unsubscribes_engine_listeners(hass: HomeAssistant) -> None:
    """HA shutting down doesn't call async_unload_entry (no config entry is unloaded, the
    process is just exiting) - the engine relies on its own EVENT_HOMEASSISTANT_STOP
    subscription, wired up in initialize(), to tear down its event/state/time listeners
    before the process exits."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    engine = entry.runtime_data
    assert engine.context.hass_api.unsubscribes

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert engine.context.hass_api.unsubscribes == []

    # idempotent - the test fixture's own teardown calls hass.async_stop(force=True), which
    # fires this same event a second time and must not raise on the already-empty list
    engine.shutdown()


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_legacy_and_new_actions_produce_same_notification(hass: HomeAssistant) -> None:
    """notify.supernotify carries Supernotify's fields in its `data:` block, supernotify.notify at
    top level - the same notification sent either way must end up identical, for every field that
    used to only be exercised with trivial top-level payloads."""
    entry = await _setup_entry(hass)
    fields = {"priority": "high", "message_html": "<b>hi</b>", "delivery_selection": "explicit"}

    await hass.services.async_call("notify", "supernotify", {"message": "same", "data": {**fields, "ttl": 5}}, blocking=True)
    await hass.async_block_till_done()
    legacy = entry.runtime_data.last_notification

    await hass.services.async_call(DOMAIN, "notify", {"message": "same", **fields, "data": {"ttl": 5}}, blocking=True)
    await hass.async_block_till_done()
    new = entry.runtime_data.last_notification

    assert legacy is not None
    assert new is not None
    assert new is not legacy
    for attr in ("priority", "message_html", "delivery_selection", "extra_data"):
        assert getattr(new, attr) == getattr(legacy, attr), attr
    assert new.priority == "high"
    assert new.message_html == "<b>hi</b>"
    assert new.extra_data == {"ttl": 5}


async def test_notify_action_migrates_nested_legacy_data(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Regression: an automation changed from notify.supernotify to supernotify.notify by renaming
    the action alone leaves priority/message_html inside `data:`, where they were archived as
    extra_data and ignored by the Notification (priority stayed at its default)."""
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"message": "restarted", "data": {"priority": "high", "message_html": "<table/>", "ttl": 5}},
        blocking=True,
    )
    await hass.async_block_till_done()

    notification = entry.runtime_data.last_notification
    assert notification is not None
    assert notification.priority == "high"
    assert notification.message_html == "<table/>"
    assert notification.extra_data == {"ttl": 5}
    assert "changed from notify.supernotify" in caplog.text


async def test_notify_action_migrates_any_nested_supernotify_field(hass: HomeAssistant) -> None:
    """Any Supernotify action field in nested data triggers the migration, not just distinctive ones -
    priority alone is enough (it is what the restart recipe's users actually hit)."""
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN, "notify", {"message": "plain", "data": {"priority": "high", "ttl": 0}}, blocking=True
    )
    await hass.async_block_till_done()

    notification = entry.runtime_data.last_notification
    assert notification is not None
    assert notification.priority == "high"
    assert notification.extra_data == {"ttl": 0}


async def test_notify_action_extra_data_is_never_migrated(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """extra_data is the escape hatch for target-service data that reuses Supernotify field names
    (e.g. a mobile_app push's own priority/actions) - passed through untouched, no warning."""
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"message": "plain", "extra_data": {"priority": "high", "actions": [{"action": "x"}], "ttl": 0}},
        blocking=True,
    )
    await hass.async_block_till_done()

    notification = entry.runtime_data.last_notification
    assert notification is not None
    assert notification.priority == "medium"
    assert notification.extra_data == {"priority": "high", "actions": [{"action": "x"}], "ttl": 0}
    assert "changed from notify.supernotify" not in caplog.text


def test_lift_legacy_nested_data_top_level_wins_and_flattens_inner_data() -> None:
    lifted = lift_legacy_nested_data({
        "priority": "low",
        "action_groups": [],  # schema-filled default must not shadow the lifted value
        "data": {"priority": "high", "action_groups": ["alarm"], "message_html": "<p/>", "data": {"ttl": 5}, "colour": "red"},
    })
    assert lifted == {
        "priority": "low",
        "action_groups": ["alarm"],
        "message_html": "<p/>",
        "data": {"colour": "red", "ttl": 5},
    }


def test_lift_legacy_nested_data_no_supernotify_fields_untouched() -> None:
    payload = {"priority": "low", "data": {"ttl": 5, "colour": "red"}}
    assert lift_legacy_nested_data(payload) == payload


def test_lift_legacy_nested_data_two_levels_of_data_is_legacy() -> None:
    assert lift_legacy_nested_data({"data": {"data": {"ttl": 5}}}) == {"data": {"ttl": 5}}


async def test_spoken_message_handled_like_message_html_by_both_actions(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)

    await hass.services.async_call(DOMAIN, "notify", {"message": "m", "spoken_message": "say new"}, blocking=True)
    await hass.async_block_till_done()
    new = entry.runtime_data.last_notification
    assert new is not None
    assert new.spoken_message == "say new"
    assert new.extra_data == {}

    await hass.services.async_call(
        "notify", "supernotify", {"message": "m", "data": {"spoken_message": "say old"}}, blocking=True
    )
    await hass.async_block_till_done()
    legacy = entry.runtime_data.last_notification
    assert legacy is not None
    assert legacy is not new
    assert legacy.spoken_message == "say old"
    assert legacy.extra_data == {}


def test_lift_legacy_nested_data_never_touches_extra_data() -> None:
    payload = {"data": {"colour": "red"}, "extra_data": {"priority": "high", "data": {"ttl": 5}, "message_html": "<p/>"}}
    assert lift_legacy_nested_data(payload) == payload


async def test_notify_action_extra_data_passed_as_data_and_wins(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"message": "plain", "data": {"colour": "red", "ttl": 1}, "extra_data": {"priority": "high", "ttl": 5}},
        blocking=True,
    )
    await hass.async_block_till_done()

    notification = entry.runtime_data.last_notification
    assert notification is not None
    assert notification.priority == "medium"
    assert notification.extra_data == {"colour": "red", "ttl": 5, "priority": "high"}


async def test_notify_description_offers_configured_names(hass: HomeAssistant) -> None:
    """supernotify.notify's delivery and scenario fields become dropdowns of what's configured, still
    taking a typed name, with tuning deliveries left to the free-form delivery_control"""
    from homeassistant.helpers.service import async_get_cached_service_description
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "delivery": {"chat": {"transport": "generic", "action": "testing.mock_notification"}},
                "scenarios": {"night": {}, "away": {}},
            }
        },
    )
    await hass.async_block_till_done()

    description = async_get_cached_service_description(hass, DOMAIN, "notify")
    assert description is not None
    fields = description["fields"]
    delivery_names = fields["delivery"]["selector"]["select"]["options"]
    assert "chat" in delivery_names
    assert fields["delivery"]["selector"]["select"]["custom_value"] is True
    assert fields["advanced"]["fields"]["delivery_control"]["selector"] == {"object": None}
    assert "delivery_selection" in fields["advanced"]["fields"]
    for field in ("require_scenarios", "apply_scenarios", "constrain_scenarios"):
        assert fields["scenarios"]["fields"][field]["selector"] == {
            "select": {"options": ["night", "away"], "multiple": True, "custom_value": True}
        }
    assert fields["message"]["required"] is True


@pytest.mark.parametrize(
    ("picked", "config", "expected"),
    [
        (None, None, {}),
        (["email"], None, {"delivery": ["email"]}),
        (None, {"email": {"data": {"cc": "a@b.com"}}}, {"delivery": {"email": {"data": {"cc": "a@b.com"}}}}),
        (["email"], "chime", {"delivery": ["email", "chime"]}),
        (["email", "chime"], ["chime", "sms"], {"delivery": ["email", "chime", "sms"]}),
        (
            ["email", "chime"],
            {"email": {"data": {"cc": "a@b.com"}}},
            {
                "delivery": {"email": {"data": {"cc": "a@b.com"}}, "chime": None},
                "delivery_selection": "explicit",
            },
        ),
        (
            ["email"],
            {"email": {"enabled": False}},
            {"delivery": {"email": {"enabled": False}}, "delivery_selection": "explicit"},
        ),
        # a legacy mapping in `delivery` itself - the config's form still wins
        ({"email": {"data": {"cc": "a@b.com"}}}, ["email"], {"delivery": {"email": None}}),
    ],
)
def test_merge_delivery_fields(picked: object, config: object, expected: dict) -> None:
    from custom_components.supernotify.actions import merge_delivery_fields

    data: dict[str, object] = {"message": "hi"}
    if picked is not None:
        data["delivery"] = picked
    if config is not None:
        data["delivery_control"] = config

    assert merge_delivery_fields(data) == {"message": "hi", **expected}


def test_merge_delivery_fields_keeps_callers_selection() -> None:
    from custom_components.supernotify.actions import merge_delivery_fields

    merged = merge_delivery_fields({
        "delivery": ["email"],
        "delivery_control": {"chime": None},
        "delivery_selection": "fixed",
    })

    assert merged["delivery_selection"] == "fixed"


async def test_notify_action_merges_delivery_dropdown_and_config(hass: HomeAssistant) -> None:
    """The deliveries picked and the free-form Delivery Config reach the notification as one
    `delivery`, with the config's tuning applied, and nothing else sent"""
    from homeassistant.setup import async_setup_component

    calls: list[ServiceCall] = []

    async def _mock_notification(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("testing", "mock_notification", _mock_notification)
    generic = {"transport": "generic", "action": "testing.mock_notification", "target_required": "never"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"delivery": {"chat": {**generic, "inclusion": ["default"]}, "pager": generic, "siren": generic}}},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "notify",
        {"message": "hello", "delivery": ["pager", "siren"], "delivery_control": {"pager": {"data": {"urgent": True}}}},
        blocking=True,
    )

    engine = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert engine.last_notification is not None
    assert list(engine.last_notification.selected_deliveries) == ["pager", "siren"]
    assert sorted(c.data.get("urgent", False) for c in calls) == [False, True]


async def _setup_delivery_choice(hass: HomeAssistant) -> list[ServiceCall]:
    from homeassistant.setup import async_setup_component

    calls: list[ServiceCall] = []

    async def _mock_notification(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("testing", "mock_notification", _mock_notification)
    generic = {"transport": "generic", "action": "testing.mock_notification", "target_required": "never"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"delivery": {"chat": {**generic, "inclusion": ["default"]}, "pager": generic, "siren": generic}}},
    )
    await hass.async_block_till_done()
    return calls


async def test_delivery_field_prefilled_with_implicit_deliveries(hass: HomeAssistant) -> None:
    from homeassistant.helpers.service import async_get_cached_service_description

    await _setup_delivery_choice(hass)

    description = async_get_cached_service_description(hass, DOMAIN, "notify")
    assert description is not None
    assert description["fields"]["delivery"]["default"] == ["chat"]
    assert {"chat", "pager", "siren"} <= set(description["fields"]["delivery"]["selector"]["select"]["options"])


@pytest.mark.parametrize(
    ("delivery", "expected"),
    [
        ("pager", {"pager"}),
        (["pager", "siren"], {"pager", "siren"}),
        # a mapping tunes deliveries without restricting to them, so the default chat is still used
        ({"pager": {"data": {"urgent": True}}}, {"chat", "pager"}),
    ],
    ids=["name", "list", "mapping"],
)
@pytest.mark.parametrize("call_style", ["supernotify.notify", "supernotify.notify legacy data", "notify.supernotify"])
async def test_delivery_block_backward_compatible(
    hass: HomeAssistant, delivery: object, expected: set[str], call_style: str
) -> None:
    """A `delivery:` name, list or mapping means the same as before the delivery dropdown and
    delivery_control were added, whichever way the action is called"""
    await _setup_delivery_choice(hass)

    if call_style == "supernotify.notify":
        await hass.services.async_call(DOMAIN, "notify", {"message": "hello", "delivery": delivery}, blocking=True)
    elif call_style == "supernotify.notify legacy data":
        await hass.services.async_call(DOMAIN, "notify", {"message": "hello", "data": {"delivery": delivery}}, blocking=True)
    else:
        await hass.services.async_call(
            "notify", "supernotify", {"message": "hello", "data": {"delivery": delivery}}, blocking=True
        )

    engine = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert engine.last_notification is not None
    assert set(engine.last_notification.selected_deliveries) == expected
    assert engine.last_notification.unknown_names == {}
