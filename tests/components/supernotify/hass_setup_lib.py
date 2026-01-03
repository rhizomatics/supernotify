"""Test fixture support"""

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

from homeassistant import config_entries, setup
from homeassistant.components.mqtt.client import MQTT
from homeassistant.components.mqtt.models import DATA_MQTT, MqttData
from homeassistant.config_entries import ConfigEntries, ConfigEntryItems
from homeassistant.const import CONF_NAME
from homeassistant.core import (
    EventBus,
    HomeAssistant,
    ServiceCall,
    ServiceRegistry,
    State,
    StateMachine,
    SupportsResponse,
)
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.yaml.loader import JSON_TYPE, parse_yaml

from custom_components.supernotify import (
    ATTR_USER_ID,
    CONF_ACTION_GROUPS,
    CONF_ACTIONS,
    CONF_ARCHIVE,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_PERSON,
    CONF_RECIPIENTS,
    CONF_SCENARIOS,
    CONF_TEMPLATE_PATH,
    CONF_TRANSPORT,
    SUPERNOTIFY_SCHEMA,
    TRANSPORT_VALUES,
)
from custom_components.supernotify.archive import NotificationArchive
from custom_components.supernotify.common import DupeChecker
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery, DeliveryRegistry
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import ATTR_OS_NAME, HomeAssistantAPI
from custom_components.supernotify.media_grab import MediaStorage
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import ScenarioRegistry
from custom_components.supernotify.snoozer import Snoozer
from custom_components.supernotify.transport import Transport

from .doubles_lib import DummyService

_LOGGER = logging.getLogger(__name__)


@dataclass
class ContextualError(Exception):
    exception: Exception
    label: str


def assert_json_round_trip(v, label=None):
    try:
        serialized: str = json.dumps(v)  # type:ignore[annotation-unchecked]
    except Exception as e:
        raise ContextualError(e, label or "unknown") from e
    try:
        deserialized: Any = json.loads(serialized)  # type:ignore[annotation-unchecked]
    except Exception as e:
        raise ContextualError(e, label or "unknown") from e
    assert deserialized, f"{label or 'unknown'} should be roundtrippable in json"


def assert_clean_notification(
    notobj: dict[str, Any] | Notification | None,
    expected_delivered: int | None = None,
    expected_skipped: int = 0,
    expected_deliveries: dict[str, int] | None = None,
    ignore_defaults: bool = True,
) -> None:
    notobj = notobj.__dict__ if isinstance(notobj, Notification) else notobj
    ignore_skipped: int = 0
    expected_suppressed: int = 0
    assert notobj is not None
    if expected_delivered is not None:
        assert notobj["delivered"] == expected_delivered
    elif expected_deliveries:
        assert notobj["delivered"] == sum(len(v.get("delivered", ())) for v in notobj["deliveries"].values())  # type: ignore
    assert notobj["failed"] == 0

    delivered_total: int = 0
    for delivery, notdelobj in notobj.get("deliveries", {}).items():
        if (
            ignore_defaults
            and delivery.startswith("DEFAULT_")
            and (expected_deliveries is None or delivery not in expected_deliveries)
        ):
            if "skipped" in notdelobj:
                ignore_skipped += 1
            elif "suppressed" in notdelobj:
                expected_suppressed += len(notdelobj["suppressed"])
        elif "delivered" in notdelobj:
            delivered_total += len(notdelobj["delivered"])
            if expected_deliveries is not None:
                assert len(notdelobj["delivered"]) == expected_deliveries.get(delivery, 0)
        elif expected_delivered is not None and expected_delivered > 0:
            assert list(notdelobj.keys()) in ([], ["deliveries"])
        elif expected_delivered is not None:
            assert list(notdelobj.keys()) == []

    if expected_delivered:
        assert delivered_total == expected_delivered

    assert notobj["skipped"] == expected_skipped + ignore_skipped
    assert notobj["suppressed"] == expected_suppressed


class MockableHomeAssistant(HomeAssistant):
    config: ConfigEntries = Mock(spec=ConfigEntries)  # type: ignore
    services: ServiceRegistry = AsyncMock(spec=ServiceRegistry)
    bus: EventBus = Mock(spec=EventBus)


def load_config(v: str | dict | list | None, return_type: type = dict) -> JSON_TYPE:
    if isinstance(v, str):
        return cast("JSON_TYPE", parse_yaml(v))
    if not v:
        return return_type()
    return v


def first_envelope(notification: Notification, delivery: str) -> Envelope:
    return notification.deliveries[delivery]["delivered"][0]  # type: ignore


class TestingContext(Context):
    """Build a test context and associated services for unit testing.

    All supernotify components are real and not mocked. HomeAssistant is optionally mocked.
    """

    __test__ = False

    def __init__(
        self,
        yaml: str | None = None,
        deliveries: ConfigType | str | None = None,
        scenarios: ConfigType | str | None = None,
        recipients: list[dict[str, Any]] | str | None = None,
        mobile_actions: ConfigType | str | None = None,
        transports: ConfigType | str | None = None,
        transport_instances: list[Transport] | None = None,
        transport_types: list[type[Transport]] | dict[type[Transport], dict[str, Any]] | None = None,
        devices: list[tuple[str, str, bool]] | None = None,
        entities: dict[str, Any] | None = None,
        hass_external_url: str | None = None,
        archive_config: ConfigType | str | None = None,
        homeassistant: HomeAssistant | None = None,
        services: dict[str, list[str]] | None = None,
        components: dict[str, dict[str, Any]] | None = None,
        media_path: Path | None = None,
        template_path: Path | None = None,
        **kwargs: Any,
    ) -> None:
        self.hass: HomeAssistant

        self.devices = {
            did: Mock(spec=DeviceEntry, id=did, disabled=False, discover=discover, identifiers=[(ddomain, did)])
            for ddomain, did, discover in devices or []
        }
        self.entities = entities or {}

        raw_config: ConfigType = cast("ConfigType", load_config(yaml))
        raw_config.setdefault("name", "Supernotify")
        raw_config.setdefault("platform", "supernotify")
        if deliveries:
            raw_config[CONF_DELIVERY] = load_config(deliveries)
        if recipients:
            raw_config[CONF_RECIPIENTS] = load_config(recipients, return_type=list)
        if scenarios:
            raw_config[CONF_SCENARIOS] = load_config(scenarios)
        if mobile_actions:
            raw_config[CONF_ACTIONS] = load_config(mobile_actions)
        if transports:
            raw_config[CONF_TRANSPORT] = load_config(transports)
        if archive_config:
            raw_config[CONF_ARCHIVE] = load_config(archive_config)
        if template_path:
            raw_config[CONF_TEMPLATE_PATH] = str(template_path)
        if media_path:
            raw_config[CONF_MEDIA_PATH] = str(media_path)
        if transport_instances:
            TRANSPORT_VALUES.extend([t.name for t in transport_instances])

        if transport_types:
            TRANSPORT_VALUES.extend([t.name for t in transport_types])

        self.config = SUPERNOTIFY_SCHEMA(raw_config)
        self.components = components

        if homeassistant is not None:  # real class or own mock
            self.hass = homeassistant
            _LOGGER.debug("TESTCONTEXT Real HomeAssistant")
        else:
            _LOGGER.debug("TESTCONTEXT Mock HomeAssistant")
            self.hass = Mock(spec=MockableHomeAssistant)
            self.hass.states = Mock(StateMachine)
            self.hass.services = Mock(ServiceRegistry)
            self.hass.services.async_call = AsyncMock()
            self.hass.config.internal_url = "http://127.0.0.1:28123"
            self.hass.config.external_url = hass_external_url or "https://my.home"
            self.hass.data = {}
            self.device_registry = AsyncMock(spec=DeviceRegistry)
            self.device_registry.devices = {did: dev for did, dev in self.devices.items() if dev.discover}
            self.device_registry.async_get = lambda did: self.devices.get(did)
            self.hass.data["device_registry"] = self.device_registry
            self.entity_registry = AsyncMock(spec=EntityRegistry)

            self.hass.data["entity_registry"] = self.entity_registry
            self.issue_registry = AsyncMock(spec=IssueRegistry)
            self.hass.data["issue_registry"] = self.issue_registry
            self.hass.data[DATA_MQTT] = Mock(spec=MqttData)
            self.hass.data[DATA_MQTT].client = AsyncMock(spec=MQTT)
            self.hass.data[DATA_MQTT].client.connected = True
            self.hass.config_entries._entries = ConfigEntryItems(self.hass)
            self.hass.loop_thread_id = 0

            for recipient in self.config.get(CONF_RECIPIENTS, []):
                if recipient.get(CONF_PERSON):
                    self.entities[recipient.get(CONF_PERSON)] = Mock(spec=State, attributes=recipient)

            self.hass.states.get.side_effect = lambda v: self.entities.get(v)

            def set_state(entity_id, v, attributes=None):  # type: ignore[possibly-missing-attribute]
                self.entities.setdefault(entity_id, Mock(spec=State, state=v, attributes=attributes or {}))
                self.entities[entity_id].state = v
                if attributes:
                    self.entities[entity_id].attributes = attributes

            self.hass.states.set.side_effect = set_state

        self.hass_external_url = hass_external_url
        if services:
            self.services = {
                f"{domain}.{action}": DummyService(self.hass, domain, action)
                for domain, actions in services.items()
                for action in actions
            }

        hass_api = HomeAssistantAPI(self.hass)
        people_registry = PeopleRegistry(self.config.get(CONF_RECIPIENTS) or [], hass_api)
        scenario_registry = ScenarioRegistry(self.config.get(CONF_SCENARIOS) or {})
        archive = NotificationArchive(self.config.get(CONF_ARCHIVE) or {}, hass_api)
        media_storage = MediaStorage(self.config.get(CONF_MEDIA_PATH), self.config.get(CONF_MEDIA_STORAGE_DAYS, 7))
        dupe_checker = DupeChecker(self.config.get(CONF_DUPE_CHECK, {}))
        if not transport_instances:
            transport_types = transport_types or TRANSPORTS

        delivery_registry = DeliveryRegistry(
            deliveries=self.config.get(CONF_DELIVERY) or {},
            transport_instances=transport_instances or None,
            transport_types=transport_types,
            transport_configs=self.config.get(CONF_TRANSPORT) or {},
        )
        self.initialized: bool = False
        super().__init__(
            hass_api,
            people_registry,
            scenario_registry,
            delivery_registry,
            dupe_checker,
            archive,
            media_storage,
            Snoozer(),
            links=self.config.get(CONF_LINKS),
            recipients=self.config.get(CONF_RECIPIENTS),
            mobile_actions=self.config.get(CONF_ACTION_GROUPS),
            cameras=self.config.get(CONF_CAMERAS),
            template_path=self.config.get(CONF_TEMPLATE_PATH),
            **kwargs,
        )

    async def test_initialize(self, transport_instances: list[Transport] | None = None) -> None:
        if transport_instances:
            self.delivery_registry._transport_instances = transport_instances
        await self.initialize()
        self.hass_api.initialize()
        if self.hass_external_url:
            self.hass_api.external_url = self.hass_external_url
        self.people_registry.initialize()
        await self.archive.initialize()
        await self.media_storage.initialize(self.hass_api)
        await self.delivery_registry.initialize(self)
        await self.scenario_registry.initialize(self.delivery_registry, self.mobile_actions, self.hass_api)
        if self.components and not isinstance(self.hass, Mock):
            for component_name, component_def in self.components.items():
                if component_name not in self.hass.config.components:
                    await setup.async_setup_component(self.hass, component_name, component_def)
            await self.hass.async_block_till_done()

        self.initialized = True

    def transport(self, transport_name: str) -> Transport:
        if self.initialized:
            return self.delivery_registry.transports[transport_name]
        return next(t for t in TRANSPORTS if t.name == transport_name)(self)

    def delivery(self, delivery_name: str) -> Delivery:
        return self.delivery_registry.deliveries[delivery_name]

    def delivery_config(self, delivery_name: str) -> dict[str, Any]:
        return self.config.get(CONF_DELIVERY, {}).get(delivery_name)

    def add_delivery(self, delivery_name: str, transport: str, **kwargs: Any) -> None:
        self.delivery_registry._config_deliveries[delivery_name] = {
            CONF_NAME: delivery_name,
            CONF_TRANSPORT: transport,
            **kwargs,
        }
        if self.initialized:
            delivery = Delivery(delivery_name, {CONF_TRANSPORT: transport, **kwargs}, self.transport(transport))
            self.delivery_registry.deliveries[delivery_name] = delivery


def register_mobile_app(
    hass_api: HomeAssistantAPI | None,
    person: str = "person.test_user",
    manufacturer: str = "xUnit",
    model: str = "PyTest001",
    device_name: str = "phone01",
    domain: str = "mobile_app",
    source: str = "unit_test",
    os_name: str = "iOS",
    user_id: str | None = None,
) -> DeviceEntry | None:

    if hass_api is None:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking")
        return None
    # hass_api.set_state(person, "home")
    existing: State | None = hass_api.get_state(person)
    if existing and existing.attributes and ATTR_USER_ID in existing.attributes:
        user_id = existing.attributes[ATTR_USER_ID]
    else:
        user_id = user_id or str(uuid.uuid1())
        attrs = dict(existing.attributes) if existing and existing.attributes else {}
        attrs[ATTR_USER_ID] = user_id
        hass_api.set_state(person, "home", attributes=attrs)

    config_entry = config_entries.ConfigEntry(
        domain=domain,
        data={ATTR_USER_ID: user_id, ATTR_OS_NAME: os_name},
        version=1,
        minor_version=1,
        unique_id=None,
        options=None,
        title=device_name,
        source=source,
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )
    try:
        hass_api._hass.config_entries._entries[config_entry.entry_id] = config_entry
        hass_api._hass.config_entries._entries._domain_index.setdefault(config_entry.domain, []).append(config_entry)
    except Exception as e:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking: %s", e)

    device_slug: str = slugify(device_name)
    if not existing or "device_trackers" not in existing.attributes:
        hass_api.set_state(
            person, "home", attributes={"user_id": user_id, "device_trackers": [f"device_tracker.mobile_app_{device_slug}"]}
        )
    else:
        trackers: list[str] = [f"device_tracker.mobile_app_{device_slug}"]
        trackers.extend(existing.attributes.get("device_trackers", []))
        hass_api.set_state(person, "home", attributes={"user_id": user_id, "device_trackers": trackers})

    device_registry = hass_api.device_registry()
    device_entry = None
    if device_registry:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            manufacturer=manufacturer,
            model=model,
            name=device_name,
            identifiers={(domain, f"device-id_{device_slug}")},
        )

    if hass_api._hass.services and device_entry:

        def fake_service(service: ServiceCall) -> None:
            _LOGGER.debug("Fake service called with service call: %s", service)

        # device.name seems to be derived from title, not the name supplied here
        hass_api._hass.services.async_register(
            "notify", slugify(f"mobile_app_{device_name}"), service_func=fake_service, supports_response=SupportsResponse.NONE
        )
    entity_registry: EntityRegistry | None = hass_api.entity_registry()
    if entity_registry and device_entry:
        entity_registry.async_get_or_create("device_tracker", "mobile_app", device_name, device_id=device_entry.id)
    hass_api.build_mobile_app_cache()
    return device_entry


def register_device(
    hass_api: HomeAssistantAPI | None = None,
    device_id: str = "00001111222233334444555566667777",
    domain: str = "unit_testing",
    domain_id: str = "test_01",
    title: str = "test fixture",
    model: str | None = None,
    identifiers: Any = None,
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
    if hass_api is None:
        _LOGGER.warning("Unable to mess with HASS config entries for device registry")
        return None
    try:
        hass_api._hass.config_entries._entries[config_entry.entry_id] = config_entry
        hass_api._hass.config_entries._entries._domain_index.setdefault(config_entry.domain, []).append(config_entry)
    except Exception as e:
        _LOGGER.warning("Unable to mess with HASS config entries for device registry: %s", e)
    device_registry = hass_api.device_registry()
    device_entry = None
    if device_registry:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            model=model,
            identifiers=identifiers or {(domain, f"{domain_id}")},
        )
    return device_entry
