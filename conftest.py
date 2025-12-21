import io
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from ssl import SSLContext
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from homeassistant.components.mqtt.client import MQTT
from homeassistant.components.mqtt.models import DATA_MQTT, MqttData
from homeassistant.components.notify.const import DOMAIN
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntryItems
from homeassistant.const import (
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import HomeAssistant, ServiceRegistry, State, StateMachine, SupportsResponse, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.helpers.template import Template
from pytest_httpserver import HTTPServer

from custom_components.supernotify import CONF_MOBILE_APP_ID, CONF_MOBILE_DEVICES, CONF_MOBILE_DISCOVERY, CONF_PERSON
from custom_components.supernotify.archive import NotificationArchive
from custom_components.supernotify.common import DupeChecker
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery, DeliveryRegistry
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.media_grab import MediaStorage
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import Scenario, ScenarioRegistry
from custom_components.supernotify.snoozer import Snoozer
from custom_components.supernotify.transport import Transport
from custom_components.supernotify.transports.chime import ChimeTransport
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from tests.components.supernotify.doubles_lib import MockImageEntity
from tests.components.supernotify.hass_setup_lib import MockableHomeAssistant

IMAGE_PATH: Path = Path("tests") / "components" / "supernotify" / "fixtures" / "media"


@dataclass
class TestImage:
    contents: bytes
    path: Path
    ext: str
    mime_type: str


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
    hass.states.async_entity_ids.return_value = ["supernotify.test_1", "supernotify.test_2"]
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
    hass.loop_thread_id = "99999"
    return hass


@pytest.fixture
def mock_people_registry(mock_hass_api: HomeAssistantAPI) -> PeopleRegistry:
    registry = Mock(spec=PeopleRegistry)
    registry.hass_api = mock_hass_api
    registry.people = {
        "person.new_home_owner": {CONF_PERSON: "person.new_home_owner"},
        "person.bidey_in": {
            CONF_PERSON: "person.bidey_in",
            CONF_MOBILE_DISCOVERY: False,
            CONF_MOBILE_DEVICES: [{CONF_MOBILE_APP_ID: "mobile_app_iphone"}, {CONF_MOBILE_APP_ID: "mobile_app_nophone"}],
        },
    }
    registry.determine_occupancy.return_value = {
        STATE_HOME: [{CONF_PERSON: "person.bidey_in"}],
        STATE_NOT_HOME: [{CONF_PERSON: "person.new_home_owner"}],
    }
    registry.enabled_recipients.return_value = registry.people.values()
    return registry


@pytest.fixture
def mock_scenario_registry() -> ScenarioRegistry:
    registry = AsyncMock(spec=ScenarioRegistry)
    registry.scenarios = {}
    return registry


@pytest.fixture
def mock_delivery_registry() -> DeliveryRegistry:
    registry = AsyncMock(spec=DeliveryRegistry)
    registry.deliveries = {}
    registry.transports = {}
    return registry


@pytest.fixture
def hass_api(hass: HomeAssistant, sample_image: TestImage) -> HomeAssistantAPI:
    image_entity = MockImageEntity(sample_image.path)
    hass_api = HomeAssistantAPI(hass)
    hass_api._hass.data["image"] = Mock(spec=EntityComponent)  # type: ignore[attr-defined,union-attr]
    hass_api._hass.data["image"].get_entity = Mock(return_value=image_entity)  # type: ignore[attr-defined,union-attr]
    return hass_api


@pytest.fixture
def mock_hass_api(mock_hass: HomeAssistant) -> HomeAssistantAPI:
    mocked = AsyncMock(spec=HomeAssistantAPI)
    mocked._hass = mock_hass
    mocked._hass.get_state = Mock(return_value=Mock(spec=State))
    mocked.template = Mock(return_value=Mock(spec=Template))
    mock_http_session: AsyncMock = AsyncMock(spec=aiohttp.ClientSession)
    mock_http_session.get = AsyncMock()
    mocked.http_session.return_value = mock_http_session
    mocked.create_job = AsyncMock()
    return mocked


@pytest.fixture
def mock_context(
    mock_hass: HomeAssistant,
    mock_people_registry: PeopleRegistry,
    mock_scenario_registry: ScenarioRegistry,
    mock_hass_api: HomeAssistantAPI,
    mock_delivery_registry: DeliveryRegistry,
    tmp_path: Path,
) -> Context:
    context = Mock(spec=Context)
    context.scenario_registry = mock_scenario_registry
    context.people_registry = mock_people_registry
    context.delivery_registry = mock_delivery_registry
    context.media_storage = Mock()
    context.media_storage.media_path = tmp_path / "media"
    context.hass_api = mock_hass_api
    context.cameras = {}
    context.snoozer = Snoozer()
    context._fallback_by_default = []
    context.mobile_actions = {}
    context.hass_api.internal_url = "http://hass-dev"
    context.hass_api.external_url = "http://hass-dev.nabu.casa"
    context.template_path = tmp_path / "templates"

    mock_delivery_registry.deliveries = {
        "plain_email": Delivery("plain_email", {}, EmailTransport(context)),
        "mobile": Delivery("mobile", {}, MobilePushTransport(context)),
        "chime": Delivery("chime", {}, ChimeTransport(context)),
    }
    return context


@pytest.fixture(scope="module", params=["jpeg", "png", "gif"])
def sample_image(request) -> TestImage:
    path = IMAGE_PATH / f"example_image.{request.param}"
    return TestImage(io.FileIO(path, "rb").readall(), path, request.param, f"image/{request.param}")


@pytest.fixture
def sample_jpeg(request) -> TestImage:
    path = IMAGE_PATH / "example_image.jpeg"
    return TestImage(io.FileIO(path, "rb").readall(), path, "jpeg", "image/jpeg")


@pytest.fixture
def sample_image_entity_id(mock_hass_api: HomeAssistantAPI, sample_image: TestImage) -> str:
    image_entity = MockImageEntity(sample_image.path)
    mock_hass_api.domain_entity.return_value = Mock(return_value=image_entity)  # type: ignore[attr-defined]
    return "image.testing"


@pytest.fixture
def deliveries(mock_context: Context) -> dict[str, Delivery]:
    return mock_context.delivery_registry.deliveries


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
def dummy_scenario(mock_hass_api) -> Scenario:
    return Scenario("mockery", {}, mock_hass_api)


@pytest.fixture
def unmocked_hass_api(hass: HomeAssistant) -> HomeAssistantAPI:
    return HomeAssistantAPI(hass)


@pytest.fixture
async def unmocked_config(uninitialized_unmocked_config: Context, mock_hass: HomeAssistant) -> Context:
    config = uninitialized_unmocked_config
    await config.initialize()
    config.people_registry.initialize()
    hass_api = HomeAssistantAPI(mock_hass)
    await config.delivery_registry.initialize(uninitialized_unmocked_config)
    await config.scenario_registry.initialize(config.delivery_registry, {}, hass_api)
    return config


@pytest.fixture
def uninitialized_unmocked_config(mock_hass_api: HomeAssistantAPI, tmp_path) -> Context:
    people_registry = PeopleRegistry([], mock_hass_api)
    scenario_registry = ScenarioRegistry({})
    delivery_registry = DeliveryRegistry({})
    dupe_checker = DupeChecker({})
    media_storage = MediaStorage(tmp_path / "media", 1)
    archive = NotificationArchive({}, mock_hass_api)
    return Context(
        mock_hass_api, people_registry, scenario_registry, delivery_registry, dupe_checker, archive, media_storage, Snoozer()
    )


@pytest.fixture
def local_server(httpserver_ssl_context: SSLContext | None, socket_enabled: Any) -> Generator[HTTPServer]:
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
def skip_notifications_fixture() -> Generator[None]:
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield
