from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN

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


async def test_setup_entry_folds_archive_path_into_archive_section(hass: HomeAssistant) -> None:
    """archive_path is the one flat "user" step field that needs nesting under CONF_ARCHIVE
    before it matches SUPERNOTIFY_SCHEMA's shape."""
    entry = MockConfigEntry(domain=DOMAIN, data={"file_path": "/config/supernotify_archive"}, options={})
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


async def test_setup_entry_does_not_clobber_legacy_yaml_platform(hass: HomeAssistant) -> None:
    """If a legacy YAML `notify: - platform: supernotify` service is already registered,
    setting up a config entry must not silently overwrite it."""
    config = {
        "notify": [
            {
                CONF_NAME: "supernotify",
                CONF_PLATFORM: DOMAIN,
            }
        ]
    }
    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()
    assert hass.services.has_service("notify", "supernotify")
    legacy_service = hass.data["notify_services"][DOMAIN][0]

    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # still the legacy-registered service, config entry setup declined to re-register
    assert hass.data["notify_services"][DOMAIN][0] is legacy_service
    assert getattr(entry, "runtime_data", None) is None
