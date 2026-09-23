from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.auth.models import User
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import slugify
from homeassistant.util.yaml.loader import JSON_TYPE, parse_yaml

if TYPE_CHECKING:
    from homeassistant.helpers.area_registry import AreaEntry
    from homeassistant.helpers.floor_registry import FloorEntry
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN as SUPERNOTIFY_DOMAIN
from custom_components.supernotify.hass_api import HomeAssistantAPI

from ..hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

GROUND_FLOOR = 0
FIRST_FLOOR = 1
ATTIC_FLOOR = 2


class House:
    """A house for integration testing"""

    def __init__(
        self,
        floors: list[str] | None = None,
        areas: dict[str, str | None] | None = None,
        users: dict[str, str | None] | None = None,
        mobile_apps: dict[str, str] | None = None,
        cameras: dict[str, str | None] | None = None,
        pirs: dict[str, str | None] | None = None,
    ) -> None:
        self._floors: list[str] = floors or []
        self._areas: dict[str, str | None] = areas or {}

        self.floors: dict[str, FloorEntry] = {}
        self.areas: dict[str, AreaEntry] = {}
        # users: HA account name -> Person slug to also create and link via user_id, or None
        # for a User-only account with no Person record at all (see CONF_USER_ID in const.py -
        # a real HA mobile_app is owned by a User; a Person is a separate, optional layer)
        self.users: dict[str, str | None] = users or {}
        # populated during setup() with each account's real hass.auth user id, keyed by the
        # account name (the `users` key)
        self.user_ids: dict[str, str] = {}
        # mobile_apps: device name -> owning account name from `users`
        self.mobile_apps: dict[str, str] = mobile_apps or {}
        # cameras/pirs: entity name -> optional area slug from `areas`
        self.cameras: dict[str, str | None] = cameras or {}
        self.pirs: dict[str, str | None] = pirs or {}
        self.service_calls: dict[str, list[ServiceCall]] = {}

    async def setup(self, hass: HomeAssistant) -> None:

        self._hass = hass
        MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)

        floor_registry = fr.async_get(hass)
        area_registry = ar.async_get(hass)

        for floor_name in self._floors:
            self.floors[floor_name] = floor_registry.async_create(floor_name)

        for area, optional_floor_name in self._areas.items():
            if optional_floor_name is not None and optional_floor_name in self.floors:
                floor_id = self.floors[optional_floor_name].floor_id
                area_entry = area_registry.async_create(area, floor_id=floor_id)
            else:
                area_entry = area_registry.async_create(area)
            self.areas[area] = area_entry

        entity_registry: EntityRegistry = er.async_get(hass)
        for name, area_entry in self.areas.items():
            entry = entity_registry.async_get_or_create("notify", "alexa_devices", f"{name}_id", suggested_object_id=name)
            entity_registry.async_update_entity(entry.entity_id, area_id=area_entry.id)
            hass.states.async_set(entry.entity_id, "unknown")

        for account_name, person_slug in self.users.items():
            user: User = await hass.auth.async_create_user(account_name)
            self.user_ids[account_name] = user.id
            if person_slug is not None:
                hass.states.async_set(f"person.{person_slug}", "home", attributes={"user_id": user.id})

        if self.mobile_apps:
            hass_api = HomeAssistantAPI(hass)
            for device_name, owner in self.mobile_apps.items():
                person_slug = self.users[owner]
                person_id = f"person.{person_slug}" if person_slug is not None else None
                register_mobile_app(hass_api, person=person_id, device_name=device_name, user_id=self.user_ids[owner])
            await async_setup_component(hass, "mobile_app", {"mobile_app": {}})

        for account_name, person_slug in self.users.items():
            # registering a mobile app above may have overwritten this person's attributes
            # wholesale (it only knows about user_id/device_trackers) - merge friendly_name
            # back on now rather than racing to set it first
            if person_slug is not None:
                person_id = f"person.{person_slug}"
                existing = hass.states.get(person_id)
                attributes = dict(existing.attributes) if existing else {}
                attributes["friendly_name"] = account_name
                hass.states.async_set(person_id, existing.state if existing else "home", attributes)

        for name, camera_area in self.cameras.items():
            entry = entity_registry.async_get_or_create("camera", "generic", f"{name}_id", suggested_object_id=name)
            if camera_area:
                entity_registry.async_update_entity(entry.entity_id, area_id=self.areas[camera_area].id)
            hass.states.async_set(entry.entity_id, "idle")

        for name, pir_area in self.pirs.items():
            entry = entity_registry.async_get_or_create("binary_sensor", "generic", f"{name}_id", suggested_object_id=name)
            if pir_area:
                entity_registry.async_update_entity(entry.entity_id, area_id=self.areas[pir_area].id)
            hass.states.async_set(entry.entity_id, "off", attributes={"device_class": "motion"})

        async def fake_call_service(call: ServiceCall) -> None:
            self.service_calls.setdefault(call.domain, [])
            self.service_calls[call.domain].append(call)

        assert await async_setup_component(hass, SUPERNOTIFY_DOMAIN, {SUPERNOTIFY_DOMAIN: {}})
        await hass.async_block_till_done()

        # setting up the notify platform registers the real, entity-backed notify.send_message -
        # replace it with a stub, since these devices have no backing NotifyEntity to dispatch to
        hass.services.async_remove("notify", "send_message")
        hass.services.async_register("notify", "send_message", fake_call_service)

        for device_name in self.mobile_apps:
            service_name = slugify(f"mobile_app_{device_name}")
            hass.services.async_remove("notify", service_name)
            hass.services.async_register("notify", service_name, fake_call_service)

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

    def services_called(self, domain: str | None) -> list[str]:
        services: list[str] = []
        for service_domain, calls in self.service_calls.items():
            if domain is None or service_domain == domain:
                for call in calls:
                    if call.service:
                        services.append(call.service)
        return sorted(services)

    def calls_by_domain(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for service_domain, calls in self.service_calls.items():
            result[service_domain] = len(calls)
        return result
