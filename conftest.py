from collections.abc import Generator
from pathlib import Path
from ssl import SSLContext
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.mqtt.client import MQTT
from homeassistant.components.mqtt.models import DATA_MQTT, MqttData
from homeassistant.components.notify.const import DOMAIN
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import (
    ATTR_STATE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import EventBus, HomeAssistant, ServiceRegistry, State, StateMachine, SupportsResponse, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.helpers.template import Template
from pytest_httpserver import HTTPServer

from custom_components.supernotify import (
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
)
from custom_components.supernotify.context import Context, HomeAssistantAccess
from custom_components.supernotify.delivery import Delivery
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


@pytest.fixture
def mock_device_registry() -> DeviceRegistry:
    return Mock(spec=DeviceRegistry)


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
    hass.config.internal_url = "http://127.0.0.1:28123"
    hass.config.external_url = "https://my.home"
    hass.data = {}
    hass.data["device_registry"] = mock_device_registry
    hass.data["entity_registry"] = mock_entity_registry
    hass.data["issue_registry"] = mock_issue_registry
    hass.data[DATA_MQTT] = Mock(spec=MqttData)
    hass.data[DATA_MQTT].client = AsyncMock(spec=MQTT)
    hass.data[DATA_MQTT].client.connected = True
    hass.config_entries._entries = {}
    hass.config_entries._domain_index = {}
    return hass


@pytest.fixture
def mock_people_registry(mock_hass_access: HomeAssistantAccess) -> PeopleRegistry:
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
def mock_hass_access(mock_hass: HomeAssistant) -> HomeAssistantAccess:
    mocked = AsyncMock(spec=HomeAssistantAccess)
    mocked._hass = mock_hass
    mocked._hass.get_state = Mock(return_value=Mock(spec=State))
    mocked.template = Mock(return_value=Mock(spec=Template))
    return mocked


@pytest.fixture
def mock_context(
    mock_hass: HomeAssistant,
    mock_people_registry: PeopleRegistry,
    mock_scenario_registry: ScenarioRegistry,
    mock_hass_access: HomeAssistantAccess,
) -> Context:
    context = Mock(spec=Context)
    context.hass = mock_hass
    context.scenario_registry = mock_scenario_registry
    context.people_registry = mock_people_registry
    context.hass_access = mock_hass_access
    context.cameras = {}
    context.snoozer = Snoozer()
    context._fallback_by_default = []
    context.mobile_actions = {}
    context.hass_internal_url = "http://hass-dev"
    context.hass_external_url = "http://hass-dev.nabu.casa"
    context.media_path = Path("/nosuchpath")
    context.template_path = Path("/templates_here")

    context.deliveries = {
        "plain_email": Delivery("plain_email", {}, EmailTransport(mock_hass, context, mock_people_registry)),
        "mobile": Delivery("mobile", {}, MobilePushTransport(mock_hass, context, mock_people_registry)),
        "chime": Delivery("chime", {}, ChimeTransport(mock_hass, context, mock_people_registry)),
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
async def superconfig(uninitialized_superconfig: Context) -> Context:
    await uninitialized_superconfig.initialize()
    return uninitialized_superconfig


@pytest.fixture
def uninitialized_superconfig(
    mock_people_registry: PeopleRegistry,
    mock_hass_access: HomeAssistantAccess,
    mock_scenario_registry: ScenarioRegistry,
    mock_hass: HomeAssistant,
) -> Context:
    return Context(mock_hass_access, mock_people_registry, mock_scenario_registry, Snoozer(), mock_hass)


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
