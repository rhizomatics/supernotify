from __future__ import annotations

import logging
from collections.abc import Generator, Mapping
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.components.person import ATTR_USER_ID
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_CONDITIONS,
    CONF_DEVICE_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.target import TargetSelection, async_extract_referenced_entity_ids
from homeassistant.util import slugify
from yarl import URL

from .compat import vol

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable, Iterable

    import aiohttp
    from anyio import Path
    from homeassistant.core import CALLBACK_TYPE, HomeAssistant, Service, ServiceResponse, State
    from homeassistant.helpers.entity_registry import EntityRegistry
    from homeassistant.helpers.typing import ConfigType
    from homeassistant.util.event_type import EventType

    from .schema import ConditionsFunc

import socket
import threading
from contextlib import contextmanager
from datetime import timedelta
from ipaddress import ip_address, ip_network
from typing import cast

import homeassistant.components.camera as ha_camera
import homeassistant.components.image as ha_image
from homeassistant.components import network
from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.group import expand_entity_ids
from homeassistant.components.trace.models import ActionTrace
from homeassistant.const import ATTR_DOMAIN, ATTR_SERVICE, EVENT_SERVICE_REGISTERED, EVENT_SERVICE_REMOVED
from homeassistant.core import Context as HomeAssistantContext
from homeassistant.core import Event, HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import ConditionError, ConditionErrorContainer, HomeAssistantError
from homeassistant.helpers import condition as condition_helper
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.network import get_url
from homeassistant.helpers.template import Template
from homeassistant.helpers.trace import trace_get, trace_path
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .common import spoken_name
from .const import CONF_DEVICE_LABELS, CONF_DEVICE_TRACKER, CONF_MOBILE_APP_ID
from .model import ConditionVariables, SelectionRule

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry

# avoid importing from homeassistant.components.mobile_app.const and triggering dependency chain

CONF_USER_ID = "user_id"
ATTR_OS_NAME = "os_name"
ATTR_OS_VERSION = "os_version"
ATTR_APP_VERSION = "app_version"
ATTR_DEVICE_NAME = "device_name"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"

MOBILE_APP_DOMAIN = "mobile_app"

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrackedDeviceDetails:
    device_id: str
    device_labels: list[str] | None = None
    mobile_app_id: str | None = None
    device_name: str | None = None
    device_tracker: str | None = None
    action: str | None = None
    user_id: str | None = None
    area_id: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    identifiers: set[tuple[str, str]] | None = None

    def as_dict(self) -> dict[str, str | list[str] | None]:
        return {
            CONF_MOBILE_APP_ID: self.mobile_app_id,
            ATTR_DEVICE_NAME: self.device_name,
            CONF_DEVICE_ID: self.device_id,
            CONF_USER_ID: self.user_id,
            CONF_DEVICE_TRACKER: self.device_tracker,
            CONF_ACTION: self.action,
            ATTR_OS_NAME: self.os_name,
            ATTR_OS_VERSION: self.os_version,
            ATTR_APP_VERSION: self.app_version,
            ATTR_MANUFACTURER: self.manufacturer,
            ATTR_MODEL: self.model,
            CONF_DEVICE_LABELS: self.device_labels,
        }

    def __eq__(self, other: object) -> bool:
        """Test support"""
        as_dict = getattr(other, "as_dict", None)
        return other is not None and callable(as_dict) and as_dict() == self.as_dict()


@dataclass
class TargetSelectorResolution:
    """Outcome of resolving area/floor/label selectors to the entities they reference"""

    entity_ids: list[str] = field(default_factory=list)
    missing_areas: list[str] = field(default_factory=list)
    missing_floors: list[str] = field(default_factory=list)
    missing_labels: list[str] = field(default_factory=list)

    def has_missing(self) -> bool:
        return bool(self.missing_areas or self.missing_floors or self.missing_labels)


def ha_device_info(entry_id: str) -> dr.DeviceInfo:
    """Home Assistant device-registry DeviceInfo for the single 'SuperNotify' device.

    Groups the platform entities in binary_sensor.py/sensor.py/switch.py (scenario/recipient
    state and control, notification/failure counters) under one device in the HA device
    registry. Unrelated to `TrackedDeviceDetails` above, which describes a discovered mobile_app
    device for targeting.
    """
    return dr.DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Supernotify",
        manufacturer="Supernotify",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


def ha_transport_device_info(entry_id: str, name: str, title: str) -> dr.DeviceInfo:
    """Home Assistant device-registry DeviceInfo for one transport, as a service, holding its
    switch and its deliveries', in its subentry - as the SMTP integration has a service device
    for each mail server"""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_transport_{name}")},
        name=title,
        manufacturer="Supernotify",
        model="Transport",
        entry_type=dr.DeviceEntryType.SERVICE,
    )


def _describe_unsubscribe(unsub: Callable[[], Any]) -> str:
    """A short, cheap label for an unsubscribe callable, for logging.

    Never str() the callable itself: the one returned by async_track_state_change_event is a
    partial over Home Assistant's shared dict of every state-change listener in the instance,
    so rendering it formats all of them on the event loop (megabytes on a large instance),
    and `%.100s` only truncates after the whole string has been built.
    """
    target = getattr(unsub, "func", unsub)  # functools.partial -> the wrapped function
    return str(getattr(target, "__qualname__", type(target).__name__))


class HomeAssistantAPI:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass: HomeAssistant = hass
        # set explicitly, else worked out by Home Assistant each time they're used
        self._internal_url: str | None = None
        self._external_url: str | None = None
        self.language: str = ""
        self.hass_name: str = "!UNDEFINED!"
        self._stores: dict[str, Store[Any]] = {}
        self._service_info: dict[tuple[str, str], Any] = {}
        self.unsubscribes: list[CALLBACK_TYPE] = []
        self._mobile_apps_by_tracker: dict[str, TrackedDeviceDetails] = {}
        self._mobile_apps_by_app_id: dict[str, TrackedDeviceDetails] = {}
        self._mobile_apps_by_device_id: dict[str, TrackedDeviceDetails] = {}
        self._mobile_apps_by_user_id: dict[str, list[TrackedDeviceDetails]] = {}

    def initialize(self) -> None:
        """Read Home Assistant's name and language, check its URLs, and find its mobile apps"""
        self.hass_name = self._hass.config.location_name
        self.language = self._hass.config.language
        if self._url(prefer_external=False) is None:
            _LOGGER.warning("SUPERNOTIFY Internal hass url not available, defaulting to %s", self.internal_url)
        if self._url(prefer_external=True) is None:
            _LOGGER.warning("SUPERNOTIFY External hass url not available, defaulting to internal url")

        self.build_mobile_app_cache()

        _LOGGER.debug(
            "SUPERNOTIFY Configured for HomeAssistant instance %s at %s , %s",
            self.hass_name,
            self.internal_url,
            self.external_url,
        )

        if not self.internal_url or not self.internal_url.startswith("http"):
            _LOGGER.warning("SUPERNOTIFY Invalid internal hass url %s", self.internal_url)

    @property
    def internal_url(self) -> str:
        """Home Assistant's URL on the local network, else `http://<host name>:<port>`.

        Worked out each time, so it follows changes to Home Assistant's network settings.
        """
        if self._internal_url is not None:
            return self._internal_url
        port = getattr(getattr(self._hass, "http", None), "server_port", None) or 8123
        return self._url(prefer_external=False) or f"http://{socket.gethostname()}:{port}"

    @internal_url.setter
    def internal_url(self, url: str) -> None:
        self._internal_url = url

    @property
    def external_url(self) -> str:
        """Home Assistant's URL from outside the local network, else its internal one.

        Worked out each time, so it follows changes to Home Assistant's network settings, and
        includes a Home Assistant Cloud remote URL even when Cloud connects after Supernotify starts.
        """
        if self._external_url is not None:
            return self._external_url
        return self._url(prefer_external=True) or self.internal_url

    @external_url.setter
    def external_url(self, url: str) -> None:
        self._external_url = url

    def _url(self, prefer_external: bool) -> str | None:
        try:
            return get_url(self._hass, prefer_external=prefer_external)
        except Exception:
            return None

    def disconnect(self) -> None:
        """Cancel every listener and timer subscribed through this API"""
        while self.unsubscribes:
            unsub = self.unsubscribes.pop()
            try:
                _LOGGER.debug("SUPERNOTIFY Unsubscribing: %s", _describe_unsubscribe(unsub))
                unsub()
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY Failed to unsubscribe: %s", e)
        _LOGGER.debug("SUPERNOTIFY Disconnection complete")

    def subscribe_event(self, event: EventType[Any] | str, callback: Callable) -> None:
        """Listen for an event on Home Assistant's bus, until disconnect()"""
        self.unsubscribes.append(self._hass.bus.async_listen(event, callback))

    def subscribe_mobile_app_changes(self, on_change: Callable[[], Awaitable[None]], cooldown: float = 10) -> None:
        """Call `on_change` once things settle after a mobile_app device, or its notify action, comes or goes

        Re-pairing or renaming a phone changes its notify action, and HA registers that action a
        little after the device itself, so both kinds of change are debounced into one call
        """
        debouncer: Debouncer = Debouncer(self._hass, _LOGGER, cooldown=cooldown, immediate=False, function=on_change)

        @callback
        def on_device(event: Event) -> None:
            device_id: str | None = event.data.get("device_id")
            if event.data.get("action") == "remove":
                relevant: bool = device_id in self._mobile_apps_by_device_id
            else:
                dev_reg: DeviceRegistry | None = self._device_registry()
                device = dev_reg.async_get(device_id) if dev_reg and device_id else None
                relevant = device is not None and any(i and i[0] == MOBILE_APP_DOMAIN for i in device.identifiers)
            if relevant:
                debouncer.async_schedule_call()

        @callback
        def on_service(event: Event) -> None:
            if event.data.get(ATTR_DOMAIN) == "notify" and str(event.data.get(ATTR_SERVICE, "")).startswith(
                f"{MOBILE_APP_DOMAIN}_"
            ):
                debouncer.async_schedule_call()

        self.subscribe_event(dr.EVENT_DEVICE_REGISTRY_UPDATED, on_device)
        self.subscribe_event(EVENT_SERVICE_REGISTERED, on_service)
        self.subscribe_event(EVENT_SERVICE_REMOVED, on_service)
        self.unsubscribes.append(debouncer.async_cancel)

    def subscribe_state(self, entity_ids: str | Iterable[str], callback: Callable) -> None:
        """Listen for state changes of these entities, until disconnect()"""
        self.unsubscribes.append(async_track_state_change_event(self._hass, entity_ids, callback))

    def subscribe_time(self, hour: int, minute: int, second: int, callback: Callable) -> None:
        """Call back daily at this time of day, until disconnect()"""
        self.unsubscribes.append(async_track_time_change(self._hass, callback, hour=hour, minute=minute, second=second))

    def subscribe_interval(self, seconds: int, callback: Callable) -> None:
        """Call back every so many seconds, until disconnect()"""
        self.unsubscribes.append(async_track_time_interval(self._hass, callback, timedelta(seconds=seconds)))

    def in_hass_loop(self) -> bool:
        """Whether running on Home Assistant's event loop, rather than in an executor thread"""
        return self.hass_avail("loop_thread_id") and self._hass.loop_thread_id == threading.get_ident()

    def get_state(self, entity_id: str) -> State | None:
        """The current state of an entity, or None if it has none"""
        return self._hass.states.get(entity_id)

    def is_state(self, entity_id: str, state: str) -> bool:
        """Whether an entity is currently in this state"""
        return self._hass.states.is_state(entity_id, state)

    def has_service(self, domain: str, service: str) -> bool:
        """Whether this action, e.g. notify.mobile_app_pixel, is registered"""
        return self._hass.services.has_service(domain, service)

    def integration_loaded(self, domain: str) -> bool:
        # guarded like hass_avail(), as tests and docgen may run with a mock hass
        """Whether this integration has been set up in Home Assistant"""
        components = getattr(self._hass.config, "components", None) if self.hass_avail("config") else None
        return isinstance(components, set) and domain in components

    def mobile_app_action_exists(self, mobile_app_id: str) -> bool:
        """Whether a mobile app can be notified, by its notify action or its notify entity"""
        action: str = mobile_app_id.removeprefix("notify.")
        return self.has_service("notify", action) or self.get_state(f"notify.{action}") is not None

    def entity_ids_for_domain(self, domain: str) -> list[str]:
        """The entity_ids, with a state, in this domain"""
        return self._hass.states.async_entity_ids(domain)

    async def async_real_user_ids(self) -> dict[str, str]:
        """Active, non-system HA user ids mapped to their login username - for discovering
        recipients that have no Person record (see CONF_USER_ID in const.py), excluding
        internal accounts like Supervisor/Home Assistant Content that aren't real people."""
        users = await self._hass.auth.async_get_users()
        result: dict[str, str] = {}
        for user in users:
            if not user.is_active or user.system_generated:
                continue
            # same lookup HA's own user-management API uses (homeassistant/components/config/auth.py)
            username = next(
                (cred.data.get("username") for cred in user.credentials if cred.auth_provider_type == "homeassistant"),
                None,
            )
            result[user.id] = username or user.name or user.id
        return result

    def platform_for_entity(self, entity_id: str) -> str | None:
        """The integration that registered this entity (RegistryEntry.platform), if any.

        A mobile app's `notify.mobile_app_<x>` is a legacy notify action, not a registered
        entity, so it's identified from the mobile app cache instead.
        """
        entity_registry: EntityRegistry | None = self._entity_registry()
        if entity_registry:
            reg_entry: RegistryEntry | None = entity_registry.async_get(entity_id) if entity_registry else None
            if reg_entry:
                return reg_entry.platform
        if entity_id.startswith("notify.") and self.mobile_app_by_id(entity_id) is not None:
            return MOBILE_APP_DOMAIN
        return None

    def config_path(self, path: str) -> str:
        """A path relative to the Home Assistant config directory, or the path itself if absolute."""
        return self._hass.config.path(path)

    async def is_local_url(self, url: str) -> bool:
        """Whether this URL is for Home Assistant itself or somewhere local to it:

        - the host of Home Assistant's internal or external URL, or a subdomain of it - not just a
          host under the same parent domain, which for a shared one like `ui.nabu.casa` is anyone's
        - a URL allowed in `allowlist_external_urls`
        - a host all of whose addresses are on a network Home Assistant has an adapter on, or loopback
        """
        host: str | None = URL(url).host
        if not host:
            return False
        host = host.lower()
        for own_url in (self.internal_url, self.external_url):
            own_host: str | None = URL(own_url).host if own_url else None
            if own_host and (host == own_host.lower() or host.endswith(f".{own_host.lower()}")):
                return True
        if self._hass.config.is_allowed_external_url(url):
            return True
        try:
            resolved = await self._hass.loop.getaddrinfo(host, None)
            # without the scope an IPv6 link-local address comes with
            addresses = {ip_address(str(info[4][0]).partition("%")[0]) for info in resolved}
            networks = [
                ip_network(f"{ip['address']}/{ip['network_prefix']}", strict=False)
                for adapter in await network.async_get_adapters(self._hass)
                for ip in (*adapter["ipv4"], *adapter["ipv6"])
            ]
        except (OSError, ValueError) as e:
            _LOGGER.debug("SUPERNOTIFY Unable to tell if %s is local: %s", host, e)
            return False
        return bool(addresses) and all(a.is_loopback or any(a in n for n in networks) for a in addresses)

    def is_allowed_path(self, path: str) -> bool:
        """Whether Home Assistant allows files to be read from here - its media folders, `www`, and
        `allowlist_external_dirs`. Blocking, so run as a job."""
        return self._hass.config.is_allowed_path(path)

    def config_entry_title_for_entity(self, entity_id: str) -> str | None:
        """The title of the config entry that registered this entity, if any."""
        entity_registry: EntityRegistry | None = self._entity_registry()
        reg_entry: RegistryEntry | None = entity_registry.async_get(entity_id) if entity_registry else None
        if reg_entry is None or reg_entry.config_entry_id is None:
            return None
        config_entry = self._hass.config_entries.async_get_entry(reg_entry.config_entry_id)
        return config_entry.title if config_entry else None

    def device_for_entity(self, entity_id: str) -> str | None:
        """The device this entity belongs to, if any."""
        entity_registry: EntityRegistry | None = self._entity_registry()
        reg_entry: RegistryEntry | None = entity_registry.async_get(entity_id) if entity_registry else None
        return reg_entry.device_id if reg_entry else None

    def entity_spoken_names(self, entity_id: str) -> set[str]:
        """What an entity can be called, by entity_id, object_id, friendly name or alias - and by
        object_id then domain, so 'driveway camera' is camera.driveway - as spoken_name() has them"""
        domain, _, object_id = entity_id.partition(".")
        names: list[str] = [entity_id, object_id, f"{object_id} {domain}"]
        state: State | None = self._hass.states.get(entity_id)
        if state:
            names.append(state.name)
        entity_registry: EntityRegistry | None = self._entity_registry()
        reg_entry: RegistryEntry | None = entity_registry.async_get(entity_id) if entity_registry else None
        if reg_entry:
            names.extend(a for a in reg_entry.aliases if isinstance(a, str))
            # from Home Assistant 2026.11 an entity's name is composed with its device's, but the
            # friendly name stays as it was until the name is changed, so the composed one is added
            full_entity_name: Callable[[HomeAssistant, RegistryEntry], str] | None = getattr(
                er, "async_get_full_entity_name", None
            )
            if full_entity_name and (full_name := full_entity_name(self._hass, reg_entry)):
                names.append(full_name)
        return {spoken_name(n) for n in names}

    def sender_entity_ids(self, ha_context: HomeAssistantContext | None) -> list[str]:
        """The automations and scripts whose current run carries this context, i.e. what sent a notification.

        An automation or script writes its state with the context of the run it starts, and the actions
        of that run carry the same context (a script started by an automation gets it as parent), so
        the sender is the automation or script whose state has the context's id or its parent's

        WARNING: best effort only, and not to be built on further. Home Assistant has no native way
        to get the original cause of a context, so this relies on the state still carrying the
        context of that run - a later or parallel run replaces it, and a sender further up the
        chain than the parent isn't found. It also scans every automation and script state on each
        call, so callers should only use it when the answer could matter."""
        if ha_context is None:
            return []
        ids: set[str] = {i for i in (ha_context.id, ha_context.parent_id) if i}
        return [s.entity_id for s in self._hass.states.async_all(("automation", "script")) if s.context.id in ids]

    def entity_ids_named(self, name: str) -> list[str]:
        """Entities that can be called this, see entity_spoken_names()"""
        wanted: str = spoken_name(name)
        return [s.entity_id for s in self._hass.states.async_all() if wanted in self.entity_spoken_names(s.entity_id)]

    def entity_ids_for_platform(
        self, domain: str, platform: str, device_model_select: str | list[str] | dict | SelectionRule | None = None
    ) -> list[str]:
        """entity_ids in `domain` (e.g. "notify") registered by a specific integration.

        Reads the entity registry directly (not the state machine), so a freshly
        registered entity counts even before it has reported a first state.

        `device_model_select` optionally filters by the backing device's model (e.g.
        `{"exclude": ["Speaker Group"]}`), same include/exclude rule shape used elsewhere.
        """
        entity_registry = self._entity_registry()
        if not entity_registry:
            return []
        entries: list[RegistryEntry] = [
            e for e in entity_registry.entities.values() if e.domain == domain and e.platform == platform
        ]
        if device_model_select is not None:
            model_filter = SelectionRule(device_model_select)
            entries = [e for e in entries if model_filter.match(self._device_model(e.device_id))]
        return [e.entity_id for e in entries]

    def _device_model(self, device_id: str | None) -> str | None:
        if device_id is None:
            return None
        dev_entry = self.find_device(device_id)
        return dev_entry.model if dev_entry else None

    async def async_get_camera_image(self, entity_id: str, timeout: int = 10) -> ha_camera.Image | None:
        """Fetch a still image directly from a camera entity, via HA's own camera component API,
        rather than triggering the camera.snapshot service and polling the filesystem for the
        resulting file to appear."""
        try:
            return await ha_camera.async_get_image(self._hass, entity_id, timeout=timeout)
        except HomeAssistantError as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get camera image for %s: %s", entity_id, e)
            return None

    async def async_get_image_entity_image(self, entity_id: str, timeout: int = 10) -> ha_image.Image | None:
        """Fetch a still image directly from an image entity, via HA's own image component API."""
        try:
            return await ha_image.async_get_image(self._hass, entity_id, timeout=timeout)
        except HomeAssistantError as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get image from entity %s: %s", entity_id, e)
            return None

    async def load_storage(self, key: str, version: int = 1) -> Any:  # ruff: ignore[any-type]
        """Load integration state previously persisted to Home Assistant's .storage/ area,
        via HA's own Store helper, or None if nothing has been persisted yet for this key."""
        try:
            return await self._store(key, version).async_load()
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to load storage %s: %s", key, e)
            return None

    def save_storage(self, key: str, data: Any, version: int = 1) -> None:  # ruff: ignore[any-type]
        """Persist integration state to Home Assistant's .storage/ area, via HA's own Store
        helper. Fire-and-forget: the write happens in a tracked background task rather than
        blocking the caller, since this is called from both sync and async contexts.
        Sync callers include actions without @callback (e.g. clear_snoozes), which Home Assistant
        runs in its executor, so off the event loop the thread-safe hass.create_task is used.
        One Store per key, so that saves made in quick succession are written in turn, the last
        one last, rather than racing each other to the file."""
        store: Store[Any] = self._store(key, version)
        if self.in_hass_loop():
            self._hass.async_create_task(store.async_save(data), f"supernotify_save_{key}")
        else:
            self._hass.create_task(store.async_save(data), f"supernotify_save_{key}")

    def _store(self, key: str, version: int) -> Store[Any]:
        if key not in self._stores:
            self._stores[key] = Store(self._hass, version, key)
        return self._stores[key]

    def create_job(self, func: Callable, *args: Any) -> asyncio.Future[Any]:
        """Wrap a blocking function call in a HomeAssistant awaitable job"""
        return self._hass.async_add_executor_job(func, *args)

    def fire_event(
        self, event_name: str, event_data: dict[str, Any] | None = None, context: HomeAssistantContext | None = None
    ) -> None:
        """Fire an event on Home Assistant's bus"""
        self._hass.bus.async_fire(event_name, event_data, context=context)

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool | None = None,
        blocking: bool | None = None,
        debug: bool = False,
        context: HomeAssistantContext | None = None,
    ) -> ServiceResponse | None:
        """Call a Home Assistant action, returning its response, if any.

        Where `return_response` isn't given, a response is only asked for if the action always
        gives one, or may give one and `debug` is on. Where `blocking` isn't given, the call
        only waits for the action to finish if a response is wanted, or `debug` is on."""
        if return_response is None:
            # unknown service, for example defined in generic action, check if it supports response
            supports_response: SupportsResponse = self.service_info(domain, service)
            if supports_response == SupportsResponse.NONE:
                return_response = False
            elif supports_response == SupportsResponse.ONLY:
                return_response = True
            else:
                return_response = debug
        if blocking is None:
            blocking = return_response or debug

        response: ServiceResponse | None = await self._hass.services.async_call(
            domain,
            service,
            service_data=service_data,
            blocking=blocking,
            context=context,
            target=target,
            return_response=return_response,
        )
        if response is not None and debug:
            _LOGGER.info("SUPERNOTIFY Service %s.%s response: %s", domain, service, response)
        return response

    def coerce_schema(self, domain: str, service: str, data: ConfigType) -> ConfigType:
        """This action data, cut down to what the action's own schema accepts, so that extra keys
        don't fail the call - unchanged if the action or its schema can't be found"""
        if not data:
            return data
        try:
            if (domain, service) not in self._service_info:
                self.service_info(domain, service)
            service_info = self._service_info.get((domain, service))
            if not service_info:
                _LOGGER.info("SUPERNOTIFY No service found to pre-validate action data for %s.%s", domain, service)
                return data
            if not service_info.get("schema"):
                _LOGGER.info("SUPERNOTIFY No vol schema found to pre-validate action data for %s.%s", domain, service)
                return data
            service_schema = service_info["schema"]

            while service_schema is not None and not (
                isinstance(service_schema, vol.Schema) and isinstance(service_schema.schema, dict)
            ):
                if isinstance(service_schema, vol.Schema):
                    # e.g. entity services get schema wrapped as vol.Schema(vol.All(...))
                    service_schema = service_schema.schema
                elif hasattr(service_schema, "validators") and hasattr(service_schema.validators, "__iter__"):
                    # e.g. vol.All — strip extras using first dict Schema sub-validator only
                    # (don't run the full chain; other validators may require target fields not in data)
                    service_schema = next(
                        (v for v in service_schema.validators if isinstance(v, vol.Schema) or hasattr(v, "validators")), None
                    )
                else:
                    service_schema = None
            if not (isinstance(service_schema, vol.Schema) and isinstance(service_schema.schema, dict)):
                service_schema = None
                _LOGGER.info("SUPERNOTIFY Unable to find schema for %s.%s", domain, service)

            if service_schema:
                coercing_schema = service_schema.extend(
                    {},
                    extra=vol.REMOVE_EXTRA if service_schema.extra == vol.PREVENT_EXTRA else service_schema.extra,
                    required=service_schema.required,
                )
                cleaned = coercing_schema(data)
            else:
                return data
            if cleaned != data:
                _LOGGER.debug("SUPERNOTIFY Coerced data for %s.%s from %s->%s", domain, service, data, cleaned)
            return cleaned
        except Exception:
            _LOGGER.exception("SUPERNOTIFY Unable to coerce %s.%s schema for %s", domain, service, data)
            return data

    def service_info(self, domain: str, service: str) -> SupportsResponse:
        """Whether an action gives a response, cached along with its schema - SupportsResponse.NONE if it can't be found"""
        supports_response: SupportsResponse | None = None
        try:
            if (domain, service) not in self._service_info:
                service_objs: dict[str, Service] = self._hass.services.async_services_for_domain(domain)
                service_obj: Service | None = service_objs.get(service)
                if service_obj:
                    self._service_info[domain, service] = {
                        "supports_response": service_obj.supports_response,
                        "schema": service_obj.schema,
                    }
            service_info: dict[str, Any] = self._service_info.get((domain, service), {})
            supports_response = service_info.get("supports_response")
            if supports_response is None:
                _LOGGER.debug("SUPERNOTIFY Unable to find service info for %s.%s", domain, service)

        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get service info for %s.%s: %s", domain, service, e)
        return supports_response or SupportsResponse.NONE  # default to no response

    def resolve_target_selectors(
        self,
        area_ids: list[str] | None = None,
        floor_ids: list[str] | None = None,
        label_ids: list[str] | None = None,
    ) -> TargetSelectorResolution:
        """Resolve HA area/floor/label selectors to the entities they reference, through the same
        core helper as HA entity actions, so groups are expanded and entities inherit the area of
        their device.
        """
        resolution = TargetSelectorResolution()
        if not (area_ids or floor_ids or label_ids):
            return resolution
        selection: dict[str, list[str]] = {}
        if area_ids:
            selection[ATTR_AREA_ID] = list(area_ids)
        if floor_ids:
            selection[ATTR_FLOOR_ID] = list(floor_ids)
        if label_ids:
            selection[ATTR_LABEL_ID] = list(label_ids)
        try:
            selected = async_extract_referenced_entity_ids(self._hass, TargetSelection(selection), expand_group=True)
            resolution.entity_ids = sorted(selected.referenced | selected.indirectly_referenced)
            resolution.missing_areas = sorted(selected.missing_areas)
            resolution.missing_floors = sorted(selected.missing_floors)
            resolution.missing_labels = sorted(selected.missing_labels)
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to resolve target selectors %s: %s", selection, e)
        return resolution

    def resolve_target_exclusion(self, exclude: dict[str, list[str]]) -> tuple[set[str], set[str]]:
        """Entity ids and device ids an `exclude` block of a target leaves out, as Home Assistant
        2026.11 does for entity actions - config and diagnostic entities included, and with the
        members of any group, so one can't come back when its group is expanded.
        """
        try:
            selected = async_extract_referenced_entity_ids(
                self._hass, TargetSelection(exclude), expand_group=True, primary_entities_only=False
            )
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to resolve target exclusion %s: %s", exclude, e)
            return set(), set()
        entity_ids: set[str] = selected.referenced | selected.indirectly_referenced
        for entity_id in list(entity_ids):
            entity_ids.update(self.group_members(entity_id) or [])
        return entity_ids, set(selected.referenced_devices)

    def find_service(self, domain: str, module: str) -> str | None:
        """The action, as `domain.service`, implemented by code in this Python module, e.g. a legacy
        notify platform's, skipping per-target actions that ignore any target given"""
        try:
            service_objs: dict[str, Service] = self._hass.services.async_services_for_domain(domain)
            if service_objs:
                for service, domain_obj in service_objs.items():
                    if domain_obj.job is not None:
                        target = domain_obj.job.target
                        bound_self = getattr(target, "__self__", None)
                        target_module: str | None = bound_self.__module__ if bound_self is not None else target.__module__
                        if target_module == module:
                            # Legacy notify platforms with a targets property (e.g. alexa_media_player)
                            # register extra per-target services (notify.<platform>_<device>) that share
                            # this same bound method but hard-code their own target, ignoring any target:
                            # passed by the caller - skip those and hold out for the base platform service.
                            registered_targets = getattr(bound_self, "registered_targets", None)
                            if registered_targets is not None and service in registered_targets:
                                continue
                            _LOGGER.debug("SUPERNOTIFY Found service %s for domain %s in %s", service, domain, module)
                            return f"{domain}.{service}"

            _LOGGER.debug("SUPERNOTIFY Unable to find service for %s, module %s", domain, module)
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to find service for %s, module %s : %s", domain, module, e)
        return None

    def smtp_recipients(self) -> dict[str, str]:
        """E-mail address of each recipient set up in Home Assistant's SMTP integration, to its notify entity"""
        recipients: dict[str, str] = {}
        registry: er.EntityRegistry | None = self._entity_registry()
        if registry is None or not self.hass_avail("config_entries"):
            return recipients
        try:
            for entry in self._hass.config_entries.async_entries("smtp", include_ignore=False, include_disabled=False):
                for subentry in entry.subentries.values():
                    # the smtp integration gives each recipient's notify entity the unique id `<entry id>_<address>`
                    if subentry.unique_id and (
                        entity_id := registry.async_get_entity_id("notify", "smtp", f"{entry.entry_id}_{subentry.unique_id}")
                    ):
                        recipients[subentry.unique_id] = entity_id
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to find SMTP recipients: %s", e)
        return recipients

    @property
    def media_dirs(self) -> dict[str, str]:
        """Folders Home Assistant's media source serves, by their name in `media-source://media_source/<name>/`"""
        return dict(self._hass.config.media_dirs)

    def find_config_entry_data(self, domain: str) -> Mapping[str, Any] | None:
        """Return the data of the first enabled, non-ignored config entry for domain, if any."""
        if not self.hass_avail("config_entries"):
            return None
        try:
            entries = self._hass.config_entries.async_entries(domain, include_ignore=False, include_disabled=False)
            if entries:
                return entries[0].data
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to find config entry for %s: %s", domain, e)
        return None

    def http_session(self) -> aiohttp.ClientSession:
        """Client aiohttp session for async web requests"""
        return async_get_clientsession(self._hass)

    async def translations(self, category: str, language: str | None = None) -> dict[str, str]:
        """Supernotify's own strings for a translation category, in the given language or else the
        configured one, keyed `component.supernotify.<category>.<key>`, English filling in any not translated"""
        return await async_get_translations(self._hass, language or self._hass.config.language, category, [DOMAIN])

    def expand_group(self, entity_ids: str | list[str]) -> list[str]:
        """These entity_ids, with any groups among them replaced by their members"""
        return expand_entity_ids(self._hass, entity_ids)

    def group_members(self, entity_id: str, _seen: set[str] | None = None) -> list[str] | None:
        """Fully expanded members of a `group.*` helper or a platform group (media_player, light... groups
        created by the group integration expose members in an `entity_id` state attribute). None if not a group.

        Other entities, e.g. `scene.*` or min/max `sensor.*`, also expose an `entity_id` attribute, so anything
        outside the `group` domain is only treated as a group if the entity registry says its platform is `group`.
        """
        if not self.hass_avail("states"):
            return None
        state = self._hass.states.get(entity_id)
        members = state.attributes.get(ATTR_ENTITY_ID) if state else None
        if not isinstance(members, (list, tuple)):
            return None
        if entity_id.partition(".")[0] != GROUP_DOMAIN and self.platform_for_entity(entity_id) != GROUP_DOMAIN:
            return None
        seen: set[str] = _seen if _seen is not None else set()
        seen.add(entity_id)
        expanded: list[str] = []
        for member in members:
            if member in seen:
                continue
            nested = self.group_members(member, seen)
            for e in nested if nested is not None else [member]:
                if e not in expanded:
                    expanded.append(e)
        return expanded

    def template(self, template_format: str) -> Template:
        """A Home Assistant template for this text"""
        return Template(template_format, self._hass)

    def hass_avail(self, property: str) -> bool:
        """Guard for HA functionality, largely for tests or docgen"""
        return self._hass is not None and getattr(self._hass, property, None) is not None

    async def register_web_path(self, media_web_path: Path | None, url_prefix: str) -> bool:
        """Serve files from this folder under this URL path, returning whether it could be done"""
        if media_web_path is None or not self.hass_avail("http"):
            return False
        try:
            from homeassistant.components.http import StaticPathConfig

            await self._hass.http.async_register_static_paths([
                StaticPathConfig(url_prefix, str(media_web_path), cache_headers=False)
            ])
            return True
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Unable to register media web exposed path for %s: %s", media_web_path, e)
        return False

    async def trace_conditions(
        self,
        conditions: ConditionsFunc,
        condition_variables: ConditionVariables,
        trace_name: str | None = None,
    ) -> tuple[bool | None, ActionTrace | None]:
        """Evaluate conditions, as evaluate_conditions() does, with a trace of how they were evaluated"""
        result: bool | None = None
        this_trace: ActionTrace | None = None
        with trace_action(self._hass, trace_name or "anon_condition") as cond_trace:
            cond_trace.set_trace(trace_get())
            this_trace = cond_trace
            with trace_path(["condition", "conditions"]) as _tp:
                result = self.evaluate_conditions(conditions, condition_variables)
            _LOGGER.debug(cond_trace.as_dict())
        return result, this_trace

    async def build_conditions(
        self, condition_config: list[ConfigType], strict: bool = False, validate: bool = False, name: str = DOMAIN
    ) -> ConditionsFunc | None:
        """A function evaluating these conditions, from their configuration.

        `validate` checks the configuration against Home Assistant's condition schemas first.
        `strict` also warns about entities that don't exist yet, and evaluates every template
        once in strict mode, even those a compound condition would skip, so that an undefined
        variable fails now rather than when a notification is sent. Raises the first problem found."""
        capturing_logger: ConditionErrorLoggingAdaptor = ConditionErrorLoggingAdaptor(_LOGGER)
        condition_variables: ConditionVariables = ConditionVariables()
        cond_list: list[ConfigType]
        try:
            if validate:
                cond_list = cast(
                    "list[ConfigType]", await condition_helper.async_validate_conditions_config(self._hass, condition_config)
                )
            else:
                cond_list = condition_config
        except Exception:
            _LOGGER.exception("SUPERNOTIFY Conditions validation failed")
            raise
        try:
            if strict:
                # can't be an error, the entity may belong to an integration that hasn't loaded yet
                for cond in cond_list:
                    for entity_id in sorted(condition_helper.async_extract_entities(cond)):
                        if self._hass.states.get(entity_id) is None:
                            _LOGGER.warning("SUPERNOTIFY Condition for %s refers to unknown entity %s", name, entity_id)
                force_strict_template_mode(cond_list, undo=False)

            test: ConditionsFunc = await condition_helper.async_conditions_from_config(
                self._hass, cond_list, cast("logging.Logger", capturing_logger), name
            )
            test(condition_variables.as_dict())
            if strict:
                # compound conditions short-circuit, so a nested template may never have been
                # reached by the evaluation above - check each one on its own, unless it
                # can't be evaluated yet for lack of its entity
                for template_cond in nested_template_conditions(cond_list):
                    if any(self._hass.states.get(e) is None for e in condition_helper.async_extract_entities(template_cond)):
                        continue
                    force_strict_template_mode([template_cond], undo=False)
                    try:
                        nested_test: ConditionsFunc = await condition_helper.async_conditions_from_config(
                            self._hass, [template_cond], cast("logging.Logger", capturing_logger), name
                        )
                        nested_test(condition_variables.as_dict())
                    finally:
                        force_strict_template_mode([template_cond], undo=True)
            return test
        except Exception:
            _LOGGER.exception("SUPERNOTIFY Conditions eval failed")
            raise
        finally:
            if strict:
                force_strict_template_mode(condition_config, undo=True)
            if strict and capturing_logger.condition_errors and len(capturing_logger.condition_errors) > 0:
                for exception in capturing_logger.condition_errors:
                    _LOGGER.warning("SUPERNOTIFY Invalid condition %s:%s", condition_config, exception)
                raise capturing_logger.condition_errors[0]

    def evaluate_conditions(
        self,
        conditions: ConditionsFunc,
        condition_variables: ConditionVariables,
    ) -> bool | None:
        """Evaluate conditions built by build_conditions() with these variables, raising any error"""
        try:
            if not condition_variables:
                _LOGGER.warning("SUPERNOTIFY No cond vars provided for condition")
            return conditions(condition_variables.as_dict() if condition_variables is not None else None)
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Condition eval failed: %s", e)
            raise

    def abs_url(self, fragment: str | None, prefer_external: bool = True) -> str | None:
        """An absolute URL for this path, against the external URL, else the internal one -
        unchanged if it's already absolute, None if there's no path"""
        base_url = self.external_url if prefer_external else self.internal_url
        if fragment:
            if fragment.startswith("http"):
                return fragment
            if fragment.startswith("/"):
                return base_url + fragment
            return base_url + "/" + fragment
        return None

    def raise_issue(
        self,
        issue_id: str,
        issue_key: str,
        issue_map: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        learn_more_url: str = "https://supernotify.rhizomatics.org.uk",
        is_fixable: bool = False,
    ) -> None:
        """Raise a repair, its text from the `issues.<issue_key>` translation, filled in from `issue_map`"""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            issue_id,
            translation_key=issue_key,
            translation_placeholders=issue_map,
            severity=severity,
            learn_more_url=learn_more_url,
            is_fixable=is_fixable,
        )

    def delete_issue(self, issue_id: str) -> None:
        """Remove a repair raised by raise_issue(), if it's there"""
        ir.async_delete_issue(self._hass, DOMAIN, issue_id)

    def mobile_app_by_tracker(self, device_tracker: str) -> TrackedDeviceDetails | None:
        """The mobile app with this device_tracker entity, if any"""
        return self._mobile_apps_by_tracker.get(device_tracker)

    def mobile_app_by_id(self, mobile_app_id: str) -> TrackedDeviceDetails | None:
        """The mobile app with this id, e.g. `mobile_app_pixel`, or its notify action, `notify.mobile_app_pixel`"""
        mobile_app_id = mobile_app_id.replace("notify.", "", 1) if mobile_app_id.startswith("notify.") else mobile_app_id
        return self._mobile_apps_by_app_id.get(mobile_app_id)

    def mobile_app_by_device_id(self, device_id: str) -> TrackedDeviceDetails | None:
        """The mobile app of this device, if any"""
        return self._mobile_apps_by_device_id.get(device_id)

    def mobile_app_by_user_id(self, user_id: str) -> list[TrackedDeviceDetails] | None:
        """The mobile apps registered by this Home Assistant user, if any"""
        return self._mobile_apps_by_user_id.get(user_id)

    def build_mobile_app_cache(self) -> None:
        """All enabled mobile apps"""
        entity_registry: EntityRegistry | None = self._entity_registry()
        if not entity_registry:
            _LOGGER.warning("SUPERNOTIFY Unable to discover mobile apps - no entity registry found")
            return

        # rebuilt from scratch, so a device that has gone, or been re-paired under a new name, goes too
        self._mobile_apps_by_tracker.clear()
        self._mobile_apps_by_app_id.clear()
        self._mobile_apps_by_device_id.clear()
        self._mobile_apps_by_user_id.clear()
        found: int = 0
        complete: int = 0
        for mobile_app_info in self.discover_devices(MOBILE_APP_DOMAIN):
            try:
                mobile_app_id: str = f"mobile_app_{slugify(mobile_app_info.device_name)}"
                device_tracker: str | None = None
                notify_action: str | None = None
                if self.has_service("notify", mobile_app_id):
                    notify_action = f"notify.{mobile_app_id}"
                else:
                    _LOGGER.debug("SUPERNOTIFY No notify action <%s>, so not a notifiable mobile app", mobile_app_id)

                registry_entries = entity_registry.entities.get_entries_for_device_id(mobile_app_info.device_id)
                for reg_entry in registry_entries:
                    if reg_entry.platform == "mobile_app" and reg_entry.domain == "device_tracker":
                        device_tracker = reg_entry.entity_id

                if device_tracker and notify_action:
                    complete += 1

                mobile_app_info.mobile_app_id = mobile_app_id
                mobile_app_info.device_tracker = device_tracker
                mobile_app_info.action = notify_action

                found += 1
                self._mobile_apps_by_app_id[mobile_app_id] = mobile_app_info
                self._mobile_apps_by_device_id[mobile_app_info.device_id] = mobile_app_info
                if device_tracker:
                    self._mobile_apps_by_tracker[device_tracker] = mobile_app_info
                if mobile_app_info.user_id is not None:
                    self._mobile_apps_by_user_id.setdefault(mobile_app_info.user_id, [])
                    self._mobile_apps_by_user_id[mobile_app_info.user_id].append(mobile_app_info)

            except Exception as e:
                _LOGGER.error("SUPERNOTIFY Failure examining device %s: %s", mobile_app_info, e)

        _LOGGER.info("SUPERNOTIFY Found %s enabled mobile app devices, %s complete config", found, complete)

    def device_config_info(self, device: DeviceEntry) -> dict[str, str | None]:
        """A device's OS name and version, app version and user, from the config entry that registered it"""
        results: dict[str, str | None] = {ATTR_OS_NAME: None, ATTR_OS_VERSION: None, CONF_USER_ID: None, ATTR_APP_VERSION: None}
        try:
            # HA 2026.8+ restricts devices to a single config entry
            config_entry_ids: Iterable[str] = (device.config_entry_id,)  # type: ignore[attr-defined]
        except AttributeError:
            # pre-2026.8: config_entry_id doesn't exist yet, fall back to deprecated plural set
            config_entry_ids = device.config_entries
        for config_entry_id in config_entry_ids:
            config_entry = self._hass.config_entries.async_get_entry(config_entry_id)
            if config_entry and config_entry.data:
                for attr, value in results.items():
                    results[attr] = config_entry.data.get(attr) or value
        return results

    def discover_devices(
        self,
        discover_domain: str,
        device_model_select: SelectionRule | None = None,
        device_manufacturer_select: SelectionRule | None = None,
        device_os_select: SelectionRule | None = None,
        device_area_select: SelectionRule | None = None,
        device_label_select: SelectionRule | None = None,
    ) -> list[TrackedDeviceDetails]:
        """Enabled devices registered by this integration, e.g. `mobile_app`, that every given
        selection rule matches, by model, manufacturer, OS, area and labels"""
        devices: list[TrackedDeviceDetails] = []
        dev_reg: DeviceRegistry | None = self._device_registry()
        if dev_reg is None or not hasattr(dev_reg, "devices"):
            _LOGGER.warning("SUPERNOTIFY Unable to discover devices for %s - no device registry found", discover_domain)
            return []

        all_devs = enabled_devs = found_devs = skipped_devs = 0
        all_ha_devices: Iterable[DeviceEntry]
        if isinstance(dev_reg.devices, Mapping):
            # 2026.8 HA and prior
            all_ha_devices = dev_reg.devices.values()
        else:
            all_ha_devices = dev_reg.devices  # type: ignore[assignment]
        for dev in all_ha_devices:
            all_devs += 1

            if dev.disabled:
                _LOGGER.debug("SUPERNOTIFY Excluded disabled device %s", dev.name)
            else:
                enabled_devs += 1
                for identifier in dev.identifiers:
                    if identifier and len(identifier) > 1 and identifier[0] == discover_domain:
                        _LOGGER.debug("SUPERNOTIFY Discovered %s device %s for id %s", dev.model, dev.name, identifier)
                        found_devs += 1
                        if device_model_select is not None and not device_model_select.match(dev.model):
                            _LOGGER.debug("SUPERNOTIFY Skipped dev %s, no model %s match", dev.name, dev.model)
                            skipped_devs += 1
                            continue
                        if device_manufacturer_select is not None and not device_manufacturer_select.match(dev.manufacturer):
                            _LOGGER.debug("SUPERNOTIFY Skipped dev %s, no manufacturer %s match", dev.name, dev.manufacturer)
                            skipped_devs += 1
                            continue
                        device_config_info = self.device_config_info(dev)
                        if device_os_select is not None and not device_os_select.match(device_config_info[ATTR_OS_NAME]):
                            _LOGGER.debug(
                                "SUPERNOTIFY Skipped dev %s, no OS %s match", dev.name, device_config_info[ATTR_OS_NAME]
                            )
                            skipped_devs += 1
                            continue
                        if device_area_select is not None and not device_area_select.match(dev.area_id):
                            _LOGGER.debug("SUPERNOTIFY Skipped dev %s, no area %s match", dev.name, dev.area_id)
                            skipped_devs += 1
                            continue
                        if device_label_select is not None and not device_label_select.match(dev.labels):
                            _LOGGER.debug("SUPERNOTIFY Skipped dev %s, no label %s match", dev.name, dev.labels)
                            skipped_devs += 1
                            continue
                        devices.append(
                            TrackedDeviceDetails(
                                device_id=dev.id,
                                device_name=dev.name,
                                manufacturer=dev.manufacturer,
                                model=dev.model,
                                area_id=dev.area_id,
                                user_id=device_config_info[ATTR_USER_ID],
                                os_name=device_config_info[ATTR_OS_NAME],
                                os_version=device_config_info[ATTR_OS_VERSION],
                                app_version=device_config_info[ATTR_APP_VERSION],
                                device_labels=list(dev.labels) if dev.labels else [],
                                identifiers=dev.identifiers,
                            )
                        )

                    elif identifier:
                        # HomeKit has triples for identifiers, other domains may behave similarly
                        _LOGGER.debug("SUPERNOTIFY Ignoring device %s id: %s", dev.name, identifier)
                    else:
                        _LOGGER.debug(  # type: ignore
                            "SUPERNOTIFY Unexpected %s device %s without id", dev.model, dev.name
                        )

        _LOGGER.debug("SUPERNOTIFY %s device discovery, all=%s, enabled=%s", discover_domain, all_devs, enabled_devs)
        _LOGGER.debug("SUPERNOTIFY %s device discovery, skipped=%s, found=%s", discover_domain, skipped_devs, found_devs)

        return devices

    def domain_for_device(self, device_id: str, domains: list[str]) -> str | None:
        """The first of these domains that the device is registered by, if any"""
        device_registry: DeviceRegistry | None = self._device_registry()
        if device_registry:
            device: DeviceEntry | None = self.find_device(device_id)
            if device:
                matching_domains = [d for d, _id in device.identifiers if d in domains]
                if matching_domains:
                    # TODO: limited to first domain found, unlikely to be more
                    return matching_domains[0]
            _LOGGER.warning(
                "SUPERNOTIFY A target that looks like a device_id can't be matched to supported integration: %s",
                device_id,
            )
        return None

    def _entity_registry(self) -> er.EntityRegistry | None:
        """Home Assistant's entity registry, or None where there's none, as with a mock hass in tests"""
        try:
            return er.async_get(self._hass)
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get entity registry: %s", e)
            return None

    def _device_registry(self) -> dr.DeviceRegistry | None:
        """Home Assistant's device registry, or None where there's none, as with a mock hass in tests"""
        try:
            return dr.async_get(self._hass)
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get device registry: %s", e)
            return None

    def find_device(self, device_id: str) -> DeviceEntry | None:
        """The device with this id, if any"""
        reg: DeviceRegistry | None = self._device_registry()
        if reg is None:
            return None
        try:
            return reg.async_get(device_id, include_child_devices=False)  # type: ignore[call-arg]
        except TypeError:
            # older HA
            return cast("DeviceEntry|None", reg.async_get(device_id))

    def is_own_device(self, device_id: str) -> bool:
        """True if `device_id` is this integration's own 'SuperNotify' device (see `ha_device_info`)"""
        device = self.find_device(device_id)
        return device is not None and any(domain == DOMAIN for domain, _identifier in device.identifiers)

    async def mqtt_available(self, raise_on_error: bool = True) -> bool:
        """Whether MQTT is set up and connected, waiting for it if it's still starting"""
        from homeassistant.components import mqtt

        try:
            return await mqtt.async_wait_for_mqtt_client(self._hass) is True
        except Exception:
            _LOGGER.exception("SUPERNOTIFY MQTT integration failed on available check")
            if raise_on_error:
                raise
        return False

    async def mqtt_publish(
        self,
        topic: str,
        payload: Any = None,  # ruff: ignore[any-type]
        qos: int = 0,
        retain: bool = False,
        raise_on_error: bool = True,
    ) -> None:
        """Publish this payload, as JSON, to an MQTT topic"""
        from homeassistant.components import mqtt

        try:
            await mqtt.async_publish(
                self._hass,
                topic=topic,
                payload=json_dumps(payload),
                qos=qos,
                retain=retain,
            )
        except Exception:
            _LOGGER.exception("SUPERNOTIFY MQTT publish failed to %s", topic)
            if raise_on_error:
                raise


class ConditionErrorLoggingAdaptor(logging.LoggerAdapter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.condition_errors: list[ConditionError] = []

    def capture(self, args: list | tuple | None) -> None:
        if args and isinstance(args, list | tuple):
            for arg in args:
                if isinstance(arg, ConditionErrorContainer):
                    self.condition_errors.extend(arg.errors)
                elif isinstance(arg, ConditionError):
                    self.condition_errors.append(arg)

    def error(self, msg: object, *args: object, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.error(msg, *args, **kwargs)

    def warning(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.warning(msg, *args, **kwargs)


class TemplateWrapper:
    def __init__(self, obj: Template) -> None:
        self._obj = obj

    def __getattr__(self, name: str) -> Any:  # ruff: ignore[any-type]
        if name == "async_render_to_info":
            return partial(self._obj.async_render_to_info, strict=True)
        return getattr(self._obj, name)

    def __setattr__(self, name: str, value: Any) -> None:  # ruff: ignore[any-type]
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        return self._obj.__repr__() if self._obj else "NULL TEMPLATE"


def force_strict_template_mode(conditions: list[ConfigType], undo: bool = False) -> None:
    def wrap_template(cond: ConfigType, undo: bool) -> ConfigType:
        for key, val in cond.items():
            if not undo and isinstance(val, Template) and hasattr(val, "_env"):
                cond[key] = TemplateWrapper(val)
            elif undo and isinstance(val, TemplateWrapper):
                cond[key] = val._obj
            elif isinstance(val, dict):
                wrap_template(val, undo)
        return cond

    if conditions is not None:
        conditions = [wrap_template(condition, undo) for condition in conditions]


def nested_template_conditions(conditions: list[ConfigType], nested: bool = False) -> Generator[ConfigType]:
    """Conditions using a template, inside compound (and/or/not) conditions"""
    for cond in conditions:
        if isinstance(cond.get(CONF_CONDITIONS), list):
            yield from nested_template_conditions(cond[CONF_CONDITIONS], nested=True)
        elif nested and any(isinstance(val, Template) for val in cond.values()):
            yield cond


@contextmanager
def trace_action(
    hass: HomeAssistant,
    item_id: str,
    config: dict[str, Any] | None = None,
    context: HomeAssistantContext | None = None,
) -> Generator[ActionTrace]:
    """Trace execution of a condition. The trace is kept by its caller, not in Home Assistant's own
    store of traces, whose UI only lists those of automations and scripts"""
    trace = ActionTrace(item_id, config, None, context or HomeAssistantContext())

    try:
        yield trace
    except Exception as ex:
        if item_id:
            trace.set_error(ex)
        raise
    finally:
        if item_id:
            trace.finished()
