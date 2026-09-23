from __future__ import annotations

import tempfile
from contextlib import chdir
from io import BytesIO
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock

from homeassistant.auth.models import User
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify
from homeassistant.util.yaml.loader import JSON_TYPE, parse_yaml
from PIL import Image, ImageDraw, ImageStat
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from conftest import test_image
from custom_components.supernotify import DOMAIN as SUPERNOTIFY_DOMAIN
from custom_components.supernotify.hass_api import HomeAssistantAPI
from tests.components.supernotify.doubles_lib import MockCameraEntity

from ..hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.area_registry import AreaEntry
    from homeassistant.helpers.floor_registry import FloorEntry

# a small palette of maximally-distinct colors, one per camera, stamped as a solid block onto
# that camera's still - see setup()/_camera_for_image(). Flat blocks survive the JPEG re-encode
# in write_image_from_bitmap almost losslessly (unlike fine detail or text), so a plain nearest-
# color match on the block's average is a cheap, reliable way to tell two cameras' images apart
# after the full round trip through the delivery pipeline.
_CAMERA_MARKER_COLORS: list[tuple[int, int, int]] = [
    (220, 20, 60),  # crimson
    (30, 144, 255),  # dodger blue
    (50, 205, 50),  # lime green
    (255, 165, 0),  # orange
    (148, 0, 211),  # dark violet
]
_CAMERA_MARKER_BOX = (0, 0, 96, 96)  # top-left corner, clear of the format-label text in fixtures/media


def _stamp_camera_image(color: tuple[int, int, int]) -> bytes:
    """A copy of the shared example image with a solid marker block painted over one corner,
    encoded fresh - so each camera's mock still is cheaply distinguishable from every other."""
    image = Image.open(str(test_image().path)).convert("RGB")
    ImageDraw.Draw(image).rectangle(_CAMERA_MARKER_BOX, fill=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


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
        self._cameras: dict[str, str | None] = cameras or {}
        self.pirs: dict[str, str | None] = pirs or {}
        self.service_calls: dict[str, list[ServiceCall]] = {}
        # holds the temp dir used for the zero-YAML component's default (relative) media/archive/
        # template paths, so they resolve under a throwaway directory rather than the real cwd -
        # see setup() and cleanup()
        self._media_root: tempfile.TemporaryDirectory[str] | None = None
        # camera entity_id -> the marker color stamped onto that camera's mock still in setup(),
        # used by _camera_for_image() to identify which camera a delivered image came from
        self._camera_markers: dict[str, tuple[int, int, int]] = {}

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
            entry: RegistryEntry = entity_registry.async_get_or_create(
                "notify", "alexa_devices", f"{name}_id", suggested_object_id=name
            )
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

        if self._cameras:
            camera_entities: dict[str, MockCameraEntity] = {}
            for index, (name, camera_area) in enumerate(self._cameras.items()):
                entry = entity_registry.async_get_or_create("camera", "generic", f"{name}_id", suggested_object_id=name)
                if camera_area:
                    entity_registry.async_update_entity(entry.entity_id, area_id=self.areas[camera_area].id)
                hass.states.async_set(entry.entity_id, "idle")
                color = _CAMERA_MARKER_COLORS[index % len(_CAMERA_MARKER_COLORS)]
                self._camera_markers[entry.entity_id] = color
                camera_entity = MockCameraEntity(test_image().path)
                camera_entity.bytes = _stamp_camera_image(color)  # skip load(): pre-baked per-camera still
                camera_entities[entry.entity_id] = camera_entity
            hass.data["camera"] = Mock(spec=EntityComponent)
            hass.data["camera"].get_entity = Mock(side_effect=camera_entities.get)

        for name, pir_area in self.pirs.items():
            entry = entity_registry.async_get_or_create("binary_sensor", "generic", f"{name}_id", suggested_object_id=name)
            if pir_area:
                entity_registry.async_update_entity(entry.entity_id, area_id=self.areas[pir_area].id)
            hass.states.async_set(entry.entity_id, "off", attributes={"device_class": "motion"})

        async def fake_call_service(call: ServiceCall) -> None:
            self.service_calls.setdefault(call.domain, [])
            self.service_calls[call.domain].append(call)

        # this is a zero-YAML setup - CONF_MEDIA_PATH etc default to relative paths, which
        # resolve against the process cwd. Without this, that's the repo root, and every test
        # run leaves real files behind under <repo>/supernotify/. chdir into a throwaway temp
        # dir just for this call, since MediaStorage.initialize() resolves the relative path to
        # an absolute one immediately and keeps that absolute path for the rest of this House's
        # lifetime - the cwd doesn't need to stay changed afterwards.
        self._media_root = tempfile.TemporaryDirectory(prefix="supernotify_test_")
        with chdir(self._media_root.name):
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

    def cleanup(self) -> None:
        """Remove the temp dir created in setup() for the zero-YAML media/archive/template
        paths. Call from the owning fixture's teardown."""
        if self._media_root is not None:
            self._media_root.cleanup()
            self._media_root = None

    def supernotify_device_id(self) -> str:
        """The HA device-registry id of the single 'SuperNotify' device, for tests targeting it
        (see HomeAssistantAPI.is_own_device) - not a literal constant, since HA assigns it at
        setup, but stable for the lifetime of this House.
        """
        device_registry = dr.async_get(self._hass)
        entry = self._hass.config_entries.async_entries(SUPERNOTIFY_DOMAIN)[0]
        device = device_registry.async_get_device_by_identifier((SUPERNOTIFY_DOMAIN, entry.entry_id), entry.entry_id)
        assert device is not None
        return device.id

    async def call(self, yaml_data: str) -> None:
        json: list[Any] | dict[Any, Any] | str = cast("JSON_TYPE", parse_yaml(yaml_data))
        await self._hass.services.async_call(
            SUPERNOTIFY_DOMAIN,
            "notify",
            json,
            blocking=True,
        )
        await self._hass.async_block_till_done()

    async def image_bytes(self, image_share_path: str) -> bytes:
        """Resolve a mobile-push 'image' share path (as attached to a notify call's
        service_data['data']['image'], see MediaStorage.share_path) back to the raw bytes of
        the processed file it points to, via the running engine's media storage."""
        entry = self._hass.config_entries.async_entries(SUPERNOTIFY_DOMAIN)[0]
        media_storage = entry.runtime_data.context.media_storage
        relative = image_share_path.removeprefix(media_storage.media_url_prefix).lstrip("/")
        file_path = media_storage.media_path / relative
        async with await file_path.open("rb") as f:
            return await f.read()

    async def assert_e2e(
        self,
        call_data: str,
        expected_calls: dict[str, list[str]] | None = None,
        expected_entities: dict[str, list[str]] | None = None,
        expected_images: dict[str, list[str]] | None = None,
    ) -> None:
        """Send `call_data` and assert the resulting service calls, entities and images.

        `expected_calls`/`expected_entities` mirror services_called()/entity_ids_called(), but
        per domain rather than flattened across all of them - `None` means no calls at all in
        that domain. `expected_images` lists, per domain, which camera each *distinct* image
        attached to that domain's calls came from (not one entry per call - multiple targets in
        the same domain are sent the same processed image, so it's deduplicated by share path
        first - see MediaStorage.share_path and _camera_for_image()).
        """
        await self.call(call_data)

        actual_calls: dict[str, list[str]] = {}
        actual_entities: dict[str, list[str]] = {}
        actual_image_paths: dict[str, list[str]] = {}
        for service_domain, calls in self.service_calls.items():
            for call in calls:
                if call.service:
                    actual_calls.setdefault(service_domain, [])
                    actual_calls[service_domain].append(call.service)
                if "entity_id" in call.data:
                    actual_entities.setdefault(service_domain, [])
                    actual_entities[service_domain].extend(call.data.get("entity_id", []))
                image_path = call.data.get("data", {}).get("image")
                if image_path:
                    actual_image_paths.setdefault(service_domain, [])
                    if image_path not in actual_image_paths[service_domain]:
                        actual_image_paths[service_domain].append(image_path)

        if expected_calls is None:
            assert not actual_calls
        else:
            assert expected_calls == actual_calls
        if expected_entities is None:
            assert not actual_entities
        else:
            assert expected_entities == actual_entities
        if expected_images is None:
            assert not actual_image_paths
        else:
            actual_cameras = {
                domain: [self._camera_for_image(await self.image_bytes(path)) for path in paths]
                for domain, paths in actual_image_paths.items()
            }
            assert expected_images == actual_cameras

    def _camera_for_image(self, image_data: bytes) -> str:
        """Identify which camera an image came from, by nearest match on the marker color
        stamped onto that camera's still in setup()."""
        region = Image.open(BytesIO(image_data)).convert("RGB").crop(_CAMERA_MARKER_BOX)
        sample = tuple(ImageStat.Stat(region).mean)

        def distance(color: tuple[int, int, int]) -> float:
            return sum((a - b) ** 2 for a, b in zip(sample, color, strict=True))

        return min(self._camera_markers, key=lambda entity_id: distance(self._camera_markers[entity_id]))
