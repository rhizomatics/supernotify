from collections.abc import Generator
from copy import deepcopy
from pathlib import Path
from ssl import SSLContext
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.mqtt.client import MQTT
from homeassistant.components.mqtt.models import DATA_MQTT, MqttData
from homeassistant.components.notify.const import DOMAIN
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntries, ConfigEntryItems
from homeassistant.const import (
    ATTR_STATE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import EventBus, HomeAssistant, ServiceRegistry, State, StateMachine, SupportsResponse, callback
from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from pytest_httpserver import HTTPServer

from custom_components.supernotify import (
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery, DeliveryRegistry
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import ScenarioRegistry
from custom_components.supernotify.snoozer import Snoozer
from custom_components.supernotify.transport import Transport
from custom_components.supernotify.transports.chime import ChimeTransport
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.mobile_push import MobilePushTransport


class MockableHomeAssistant(HomeAssistant):
    config: ConfigEntries = Mock(spec=ConfigEntries)  # type: ignore
    services: ServiceRegistry = AsyncMock(spec=ServiceRegistry)
    bus: EventBus = Mock(spec=EventBus)


class MockAction(BaseNotificationService):
    """A test class for notification services."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[tuple[str, str | None, str | None, dict[str, Any]]] = []

    @callback
    async def async_send_message(
        self, message: str = "", title: str | None = None, target: str | None = None, **kwargs: dict[str, Any]
    ) -> None:
        self.calls.append((message, title, target, kwargs))


class TestingContext(Context):
    def __init__(
        self,
        real_hass: bool = False,
        deliveries: dict[str, Any] | None = None,
        scenarios: ConfigType | None = None,
        recipients: list[dict[str, Any]] | None = None,
        default_scenario_for_testing: bool = False,
        mobile_actions: ConfigType | None = None,
        transport_configs: ConfigType | None = None,
        transport_instances: list[Transport] | None = None,
        transport_types: list[type[Transport]] | None = None,
        devices: list[tuple[str, str, bool]] | None = None,
        entities: dict[str, Any] | None = None,
        hass_external_url: str | None = None,
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
        self.scenarios: ConfigType = deepcopy(scenarios) if scenarios else {}
        self.recipients: list[dict[str, Any]] = deepcopy(recipients) if recipients else []
        self.transport_configs: ConfigType = deepcopy(transport_configs) if transport_configs else {}
        self.mobile_actions: ConfigType = deepcopy(mobile_actions) if mobile_actions else {}
        self.hass_external_url = hass_external_url

        hass_access = HomeAssistantAPI(self.hass)
        people_registry = PeopleRegistry(self.recipients or [], hass_access)
        scenario_registry = ScenarioRegistry(self.scenarios or {})

        if not transport_instances:
            transport_types = transport_types or TRANSPORTS

        delivery_registry = DeliveryRegistry(
            deliveries=self.deliveries or {},
            transport_instances=transport_instances or None,
            transport_types=transport_types,
            transport_configs=self.transport_configs or {},
        )

        super().__init__(hass_access, people_registry, scenario_registry, delivery_registry, Snoozer(), **kwargs)

    async def test_initialize(self, transport_instances: list[Transport] | None = None) -> None:
        if transport_instances:
            self.delivery_registry._transport_instances = transport_instances
        await self.initialize()
        self.hass_access.initialize()
        if self.hass_external_url:
            self.hass_access.external_url = self.hass_external_url
        self.people_registry.initialize()
        await self.delivery_registry.initialize(self)
        await self.scenario_registry.initialize(
            self.delivery_registry.deliveries, self.delivery_registry.default_deliveries, self.mobile_actions, self.hass_access
        )

    def transport(self, transport_name: str) -> Transport:
        return self.delivery_registry.transports[transport_name]


@pytest.fixture
def mock_device_registry() -> DeviceRegistry:
    mocked = Mock(spec=DeviceRegistry)
    mocked.devices = {}
    return mocked


@pytest.fixture
def mock_entity_registry() -> EntityRegistry:
    return Mock(spec=EntityRegistry)


@pytest.fixture
def mock_issue_registry() -> IssueRegistry:
    return Mock(spec=IssueRegistry)


@pytest.fixture
def mock_hass(
    mock_device_registry: DeviceRegistry, mock_entity_registry: EntityRegistry, mock_issue_registry: IssueRegistry
) -> HomeAssistant:
    hass = Mock(spec=MockableHomeAssistant)
    hass.states = Mock(StateMachine)
    hass.states.async_entity_ids.return_value = ["supernotify.test_1", "supernotify.test_1"]
    hass.services = Mock(ServiceRegistry)
    hass.services.async_call = AsyncMock()
    hass.config.internal_url = "http://127.0.0.1:28123"
    hass.config.external_url = "https://my.home"
    hass.data = {}
    hass.data["device_registry"] = mock_device_registry
    hass.data["entity_registry"] = mock_entity_registry
    hass.data["issue_registry"] = mock_issue_registry
    hass.data[DATA_MQTT] = Mock(spec=MqttData)
    hass.data[DATA_MQTT].client = AsyncMock(spec=MQTT)
    hass.data[DATA_MQTT].client.connected = True
    hass.config_entries._entries = ConfigEntryItems(hass)
    return hass


@pytest.fixture
def mock_people_registry(mock_hass_access: HomeAssistantAPI) -> PeopleRegistry:
    registry = Mock(spec=PeopleRegistry)
    registry.hass_access = mock_hass_access
    registry.people = {
        "person.new_home_owner": {CONF_PERSON: "person.new_home_owner", ATTR_STATE: "not_home"},
        "person.bidey_in": {
            CONF_PERSON: "person.bidey_in",
            ATTR_STATE: "home",
            CONF_MOBILE_DEVICES: [{CONF_NOTIFY_ACTION: "mobile_app_iphone"}, {CONF_NOTIFY_ACTION: "mobile_app_nophone"}],
        },
    }
    registry.determine_occupancy.return_value = {
        STATE_HOME: [{CONF_PERSON: "person.bidey_in"}],
        STATE_NOT_HOME: [{CONF_PERSON: "person.new_home_owner"}],
    }
    return registry


@pytest.fixture
def mock_scenario_registry() -> ScenarioRegistry:
    registry = AsyncMock(spec=ScenarioRegistry)
    registry.scenarios = {}
    registry.delivery_by_scenario = {}
    registry.content_scenario_templates = {}
    registry.content_scenario_templates = {}
    return registry


@pytest.fixture
def mock_delivery_registry() -> DeliveryRegistry:
    registry = AsyncMock(spec=DeliveryRegistry)
    registry.deliveries = {}
    registry.transports = {}
    registry.default_deliveries = []
    registry.default_delivery_by_transport = {}
    return registry


@pytest.fixture
def mock_hass_access(mock_hass: HomeAssistant) -> HomeAssistantAPI:
    mocked = AsyncMock(spec=HomeAssistantAPI)
    mocked._hass = mock_hass
    mocked._hass.get_state = Mock(return_value=Mock(spec=State))
    mocked.template = Mock(return_value=Mock(spec=Template))
    return mocked


@pytest.fixture
def mock_context(
    mock_hass: HomeAssistant,
    mock_people_registry: PeopleRegistry,
    mock_scenario_registry: ScenarioRegistry,
    mock_hass_access: HomeAssistantAPI,
    mock_delivery_registry: DeliveryRegistry,
) -> Context:
    context = Mock(spec=Context)
    context.scenario_registry = mock_scenario_registry
    context.people_registry = mock_people_registry
    context.delivery_registry = mock_delivery_registry
    context.hass_access = mock_hass_access
    context.cameras = {}
    context.snoozer = Snoozer()
    context._fallback_by_default = []
    context.mobile_actions = {}
    context.hass_access.internal_url = "http://hass-dev"
    context.hass_access.external_url = "http://hass-dev.nabu.casa"
    context.media_path = Path("/nosuchpath")
    context.template_path = Path("/templates_here")

    mock_delivery_registry.deliveries = {
        "plain_email": Delivery("plain_email", {}, EmailTransport(context)),
        "mobile": Delivery("mobile", {}, MobilePushTransport(context)),
        "chime": Delivery("chime", {}, ChimeTransport(context)),
    }
    return context


@pytest.fixture
def mock_notify(hass: HomeAssistant) -> MockAction:
    mock_action: MockAction = MockAction()
    hass.services.async_register(DOMAIN, "mock", mock_action, supports_response=SupportsResponse.NONE)  # type: ignore
    return mock_action


@pytest.fixture
def mock_transport() -> AsyncMock:
    m = AsyncMock(spec=Transport)
    m.name = "unit_test"
    m.delivery_config = Mock(return_value={})
    m.deliver = AsyncMock(return_value=True)
    return m


@pytest.fixture
def mock_scenario() -> AsyncMock:
    mock_scenario = AsyncMock()
    mock_scenario.name = "mockery"
    mock_scenario.media = []
    return mock_scenario


@pytest.fixture
async def unmocked_config(uninitialized_unmocked_config: Context, mock_hass: HomeAssistant) -> Context:
    config = uninitialized_unmocked_config
    await config.initialize()
    config.people_registry.initialize()
    hass_access = HomeAssistantAPI(mock_hass)
    await config.delivery_registry.initialize(uninitialized_unmocked_config)
    await config.scenario_registry.initialize(
        config.delivery_registry.deliveries, config.delivery_registry.default_deliveries, {}, hass_access
    )
    return config


@pytest.fixture
def uninitialized_unmocked_config(
    mock_hass_access: HomeAssistantAPI,
) -> Context:
    people_registry = PeopleRegistry([], mock_hass_access)
    scenario_registry = ScenarioRegistry({})
    delivery_registry = DeliveryRegistry({})
    return Context(mock_hass_access, people_registry, scenario_registry, delivery_registry, Snoozer())


@pytest.fixture
def local_server(httpserver_ssl_context: SSLContext | None, socket_enabled: Any) -> Generator[HTTPServer, None, None]:
    """pytest-socket will fail at fixture creation time, before test that uses it"""
    server = HTTPServer(host="127.0.0.1", port=0, ssl_context=httpserver_ssl_context)
    server.start()
    yield server
    server.clear()  # type: ignore
    if server.is_running():
        server.stop()  # type: ignore


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable custom integrations in all tests."""
    return


# This fixture is used to prevent HomeAssistant from attempting to create and dismiss persistent
# notifications. These calls would fail without this fixture since the persistent_notification
# integration is never loaded during a test.


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture() -> Generator[None, None, None]:
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield
