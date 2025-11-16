"""Test fixture support"""

import logging
from copy import deepcopy
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, Mock

from homeassistant import config_entries
from homeassistant.components.mqtt.client import MQTT
from homeassistant.components.mqtt.models import DATA_MQTT, MqttData
from homeassistant.config_entries import ConfigEntries, ConfigEntryItems
from homeassistant.const import CONF_NAME
from homeassistant.core import (
    EventBus,
    HomeAssistant,
    ServiceCall,
    ServiceRegistry,
    ServiceResponse,
    StateMachine,
    SupportsResponse,
)
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.yaml import parse_yaml

from custom_components.supernotify import CONF_TRANSPORT, SUPERNOTIFY_SCHEMA
from custom_components.supernotify.archive import NotificationArchive
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery, DeliveryRegistry
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import ScenarioRegistry
from custom_components.supernotify.snoozer import Snoozer
from custom_components.supernotify.transport import Transport

_LOGGER = logging.getLogger(__name__)


class MockableHomeAssistant(HomeAssistant):
    config: ConfigEntries = Mock(spec=ConfigEntries)  # type: ignore
    services: ServiceRegistry = AsyncMock(spec=ServiceRegistry)
    bus: EventBus = Mock(spec=EventBus)


class TestingContext(Context):
    """Build a test context and associated services for unit testing.

    All supernotify components are real and not mocked. HomeAssistant is optionally mocked.
    """

    __test__ = False

    @classmethod
    def from_config(cls, yaml_string: str) -> "TestingContext":
        parsed_yaml = parse_yaml(yaml_string)
        conf: ConfigType = SUPERNOTIFY_SCHEMA(parsed_yaml)
        return TestingContext(
            deliveries=conf.pop("delivery", None),
            transport_configs=conf.pop("transports", None),
            archive_config=conf.pop("archive", None),
            **conf,
        )

    def __init__(
        self,
        deliveries: dict[str, Any] | None = None,
        scenarios: ConfigType | None = None,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: ConfigType | None = None,
        transport_configs: ConfigType | None = None,
        transport_instances: list[Transport] | None = None,
        transport_types: list[type[Transport]] | None = None,
        devices: list[tuple[str, str, bool]] | None = None,
        entities: dict[str, Any] | None = None,
        hass_external_url: str | None = None,
        archive_config: ConfigType | None = None,
        homeassistant: HomeAssistant | None = None,
        **kwargs: Any,
    ) -> None:
        self.hass: HomeAssistant
        self.devices = {
            did: Mock(spec=DeviceEntry, id=did, disabled=False, discover=discover, identifiers=[(ddomain, did)])
            for ddomain, did, discover in devices or []
        }
        self.entities = entities
        if homeassistant:  # real class or own mock
            self.hass = homeassistant
        else:
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
            if self.entities:
                self.hass.states.get.side_effect = lambda v: self.entities.get(v)
            self.hass.data["entity_registry"] = self.entity_registry
            self.issue_registry = AsyncMock(spec=IssueRegistry)
            self.hass.data["issue_registry"] = self.issue_registry
            self.hass.data[DATA_MQTT] = Mock(spec=MqttData)
            self.hass.data[DATA_MQTT].client = AsyncMock(spec=MQTT)
            self.hass.data[DATA_MQTT].client.connected = True
            self.hass.config_entries._entries = ConfigEntryItems(self.hass)
        self.deliveries: dict[str, Any] = deepcopy(deliveries) if deliveries else {}
        # deepcopy of scenario breaks on Condition
        self.scenarios: ConfigType = scenarios if scenarios else {}
        self.recipients: list[dict[str, Any]] = deepcopy(recipients) if recipients else []
        self.transport_configs: ConfigType = deepcopy(transport_configs) if transport_configs else {}
        self.mobile_actions: ConfigType = deepcopy(mobile_actions) if mobile_actions else {}
        self.hass_external_url = hass_external_url

        hass_api = HomeAssistantAPI(self.hass)
        people_registry = PeopleRegistry(self.recipients or [], hass_api)
        scenario_registry = ScenarioRegistry(self.scenarios or {})
        archive = NotificationArchive(archive_config or {}, hass_api)

        if not transport_instances:
            transport_types = transport_types or TRANSPORTS

        delivery_registry = DeliveryRegistry(
            deliveries=self.deliveries or {},
            transport_instances=transport_instances or None,
            transport_types=transport_types,
            transport_configs=self.transport_configs or {},
        )
        self.initialized: bool = False
        super().__init__(hass_api, people_registry, scenario_registry, delivery_registry, archive, Snoozer(), **kwargs)

    async def test_initialize(self, transport_instances: list[Transport] | None = None) -> None:
        if transport_instances:
            self.delivery_registry._transport_instances = transport_instances
        await self.initialize()
        self.hass_api.initialize()
        if self.hass_external_url:
            self.hass_api.external_url = self.hass_external_url
        self.people_registry.initialize()
        await self.delivery_registry.initialize(self)
        await self.scenario_registry.initialize(
            self.delivery_registry.deliveries, self.delivery_registry.implicit_deliveries, self.mobile_actions, self.hass_api
        )
        self.initialized = True

    def transport(self, transport_name: str) -> Transport:
        if self.initialized:
            return self.delivery_registry.transports[transport_name]
        return next(t for t in TRANSPORTS if t.name == transport_name)(self)

    def delivery(self, delivery_name: str) -> Delivery:
        return self.delivery_registry.deliveries[delivery_name]

    def add_delivery(self, delivery_name: str, transport: str, **kwargs: Any) -> None:
        self.delivery_registry._deliveries[delivery_name] = {CONF_NAME: delivery_name, CONF_TRANSPORT: transport, **kwargs}
        if self.initialized:
            delivery = Delivery(delivery_name, {CONF_TRANSPORT: transport, **kwargs}, self.transport(transport))
            self.delivery_registry.deliveries[delivery_name] = delivery


def register_mobile_app(
    people_registry: PeopleRegistry | None,
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
    if people_registry is None or people_registry.hass_api is None or people_registry.hass_api._hass is None:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking")
        return None
    try:
        people_registry.hass_api._hass.config_entries._entries[config_entry.entry_id] = config_entry
        people_registry.hass_api._hass.config_entries._entries._domain_index.setdefault(config_entry.domain, []).append(
            config_entry
        )
    except Exception as e:
        _LOGGER.warning("Unable to mess with HASS config entries for mobile app faking: %s", e)
    people_registry.hass_api._hass.states.async_set(
        person, "home", attributes={"device_trackers": [f"device_tracker.mobile_app_{device_name}", "dev002"]}
    )

    device_registry = people_registry.hass_api.device_registry()
    device_entry = None
    if device_registry:
        device_entry = device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            manufacturer=manufacturer,
            model=model,
            identifiers={(domain, f"device-id_{device_name}")},
        )
    if people_registry.hass_api._hass and people_registry.hass_api._hass.services and device_entry:

        def fake_service(service: ServiceCall) -> None:
            _LOGGER.debug("Fake service called with service call: %s", service)

        # device.name seems to be derived from title, not the name supplied here
        people_registry.hass_api._hass.services.async_register(
            "notify", slugify(f"mobile_app_{title}"), service_func=fake_service, supports_response=SupportsResponse.NONE
        )
    entity_registry: EntityRegistry | None = people_registry.hass_api.entity_registry()
    if entity_registry and device_entry:
        entity_registry.async_get_or_create("device_tracker", "mobile_app", device_name, device_id=device_entry.id)
    return device_entry


class DummyService:
    """Dummy service for testing purposes."""

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str = "notify",
        action: str = "custom_test",
        supports_response=SupportsResponse.OPTIONAL,
        response: ServiceResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.hass = hass
        self.calls: list[ServiceCall] = []
        self.response = response
        self.exception = exception
        hass.services.async_register(domain, action, self.service_call, supports_response=supports_response)

    def service_call(self, call: ServiceCall) -> ServiceResponse | None:
        self.calls.append(call)
        if self.exception:
            raise self.exception
        return self.response


def register_device(
    hass_api: HomeAssistantAPI | None = None,
    device_id: str = "00001111222233334444555566667777",
    domain: str = "unit_testing",
    domain_id: str = "test_01",
    title: str = "test fixture",
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
    if hass_api is None or hass_api._hass is None:
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
            identifiers=identifiers or {(domain, f"{domain_id}")},
        )
    return device_entry
