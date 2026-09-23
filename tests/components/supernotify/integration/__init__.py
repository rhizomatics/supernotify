from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.util.yaml.loader import JSON_TYPE, parse_yaml

if TYPE_CHECKING:
    from homeassistant.helpers.area_registry import AreaEntry
    from homeassistant.helpers.floor_registry import FloorEntry
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN as SUPERNOTIFY_DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


class House:
    """A house for integration testing"""

    def __init__(self, floors: dict[int, FloorEntry] | None = None, areas: dict[str, AreaEntry] | None = None) -> None:
        self.floors: dict[int, FloorEntry] = floors or {}
        self.areas: dict[str, AreaEntry] = areas or {}
        self.service_calls: dict[str, list[ServiceCall]] = {}

    async def setup(self, hass: HomeAssistant) -> None:

        self._hass = hass
        MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)

        entity_registry = er.async_get(hass)
        for name, area in self.areas.items():
            entry = entity_registry.async_get_or_create("notify", "alexa_devices", f"{name}_id", suggested_object_id=name)
            entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
            hass.states.async_set(entry.entity_id, "unknown")

        async def fake_call_service(call: ServiceCall) -> None:
            self.service_calls.setdefault(call.domain, [])
            self.service_calls[call.domain].append(call)

        assert await async_setup_component(hass, SUPERNOTIFY_DOMAIN, {SUPERNOTIFY_DOMAIN: {}})
        await hass.async_block_till_done()

        # setting up the notify platform registers the real, entity-backed notify.send_message -
        # replace it with a stub, since these devices have no backing NotifyEntity to dispatch to
        hass.services.async_remove("notify", "send_message")
        hass.services.async_register("notify", "send_message", fake_call_service)

    async def call(self, yaml_data: str) -> None:
        json: list[Any] | dict[Any, Any] | str = cast("JSON_TYPE", parse_yaml(yaml_data))
        await self._hass.services.async_call(
            SUPERNOTIFY_DOMAIN,
            "notify",
            json,
            blocking=True,
        )
        await self._hass.async_block_till_done()

    def entity_ids_called(self, domain: str | None) -> list[str]:
        entity_ids: list[str] = []
        for service_domain, calls in self.service_calls.items():
            if domain is None or service_domain == domain:
                for call in calls:
                    entity_ids.extend(call.data.get("entity_id", []))
        return sorted(entity_ids)
