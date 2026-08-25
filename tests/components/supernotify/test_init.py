from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import ATTR_IMPORTED_FROM_YAML, DOMAIN
from custom_components.supernotify.const import CONF_DELIVERY, CONF_TRANSPORT

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
    """archive_path lives in the archive options section, matching SUPERNOTIFY_SCHEMA's
    nested shape directly - no folding needed between entry.data and entry.options."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={"archive": {"file_path": "/config/supernotify_archive"}})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data is not None
    assert entry.runtime_data.context.archive.configured_archive_path == "/config/supernotify_archive"


async def test_setup_entry_imported_from_yaml_skips_registration(hass: HomeAssistant) -> None:
    """An entry mirroring a YAML config never registers a second notify.supernotify -
    the legacy YAML platform already owns it."""
    entry = MockConfigEntry(domain=DOMAIN, data={ATTR_IMPORTED_FROM_YAML: True}, options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service("notify", "supernotify")
    assert getattr(entry, "runtime_data", None) is None


async def test_yaml_setup_mirrors_into_import_entry(hass: HomeAssistant) -> None:
    """The legacy YAML platform mirrors its config into a config entry, without creating a
    second notify.supernotify - and raises a deprecated_yaml repair."""
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

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[ATTR_IMPORTED_FROM_YAML] is True
    assert entries[0].title == "Supernotify (imported from YAML)"
    # the legacy YAML platform still owns the service, untouched by the mirrored entry
    assert hass.data["notify_services"][DOMAIN][0] is legacy_service

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}") is not None


async def test_yaml_with_deliveries_does_not_raise_deprecated_yaml(hass: HomeAssistant) -> None:
    """If the YAML defines deliveries/transports/scenarios/recipients/cameras/action_groups/
    links - none of which are UI-configurable yet - it can't actually be removed, so nagging
    to remove it would be wrong. The mirrored entry (for the global settings that ARE
    UI-configurable) still gets created."""
    config = {
        "notify": [
            {
                CONF_NAME: "supernotify",
                CONF_PLATFORM: DOMAIN,
                CONF_DELIVERY: {"persistent": {CONF_TRANSPORT: "persistent"}},
            }
        ]
    }
    assert await async_setup_component(hass, "notify", config)
    await hass.async_block_till_done()

    assert hass.services.has_service("notify", "supernotify")
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue("homeassistant", f"deprecated_yaml_{DOMAIN}") is None


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
