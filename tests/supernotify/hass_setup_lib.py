"""Test fixture support"""

import logging
from types import MappingProxyType

from homeassistant import config_entries
from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.util import slugify

from custom_components.supernotify.configuration import Context

_LOGGER = logging.getLogger(__name__)


def register_mobile_app(
    context: Context,
    person: str = "person.test_user",
    manufacturer: str = "xUnit",
    model: str = "PyTest001",
    device_name: str = "phone01",
    domain: str = "test",
    source: str = "unit_test",
    title: str = "Test Device",
) -> DeviceEntry | None:
    config_entry = config_entries.ConfigEntry(
        domain=domain,
        data={},
        version=1,
        minor_version=1,
        unique_id=None,
        options=None,
        title=title,
        source=source,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    if context is None or context.hass is None:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking")
        return None
    try:
        context.hass.config_entries._entries[config_entry.entry_id] = config_entry
        context.hass.config_entries._entries._domain_index.setdefault(config_entry.domain, []).append(config_entry)
    except Exception as e:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking: %s", e)
    context.hass.states.async_set(
        person, "home", attributes={"device_trackers": [f"device_tracker.mobile_app_{device_name}", "dev002"]}
    )
    device_registry = context.device_registry()
    device_entry = None
    if device_registry:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            manufacturer=manufacturer,
            model=model,
            identifiers={(domain, f"device-id_{device_name}")},
        )
    if context.hass.services and device_entry and context.hass and context.hass.services:

        def fake_service(service: ServiceCall) -> None:
            _LOGGER.debug("Fake service called with service call: %s", service)

        # device.name seems to be derived from title, not the name supplied here
        context.hass.services.async_register(
            "notify", slugify(f"mobile_app_{title}"), service_func=fake_service, supports_response=SupportsResponse.NONE
        )
    entity_registry = context.entity_registry()
    if entity_registry and device_entry:
        entity_registry.async_get_or_create("device_tracker", "mobile_app", device_name, device_id=device_entry.id)
    return device_entry


def register_device(
    context: Context,
    device_id: str = "00001111222233334444555566667777",
    domain: str = "unit_testing",
    domain_id: str = "test_01",
    title: str = "test fixture",
) -> DeviceEntry | None:
    config_entry = config_entries.ConfigEntry(
        domain=domain,
        data={},
        version=1,
        minor_version=1,
        unique_id=device_id,
        options=None,
        title=title,
        source="",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    if context is None or context.hass is None:
        _LOGGER.warning("Unable to mess with HASS config entries for device registry")
        return None
    try:
        context.hass.config_entries._entries[config_entry.entry_id] = config_entry
        context.hass.config_entries._entries._domain_index.setdefault(config_entry.domain, []).append(config_entry)
    except Exception as e:
        _LOGGER.warning("Unable to mess with HASS config entries for device registry: %s", e)
    device_registry = context.device_registry()
    device_entry = None
    if device_registry:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(domain, f"{domain_id}")},
        )
    return device_entry
