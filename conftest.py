from collections.abc import Generator
from pathlib import Path
from ssl import SSLContext
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.notify.const import DOMAIN
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntries
from homeassistant.const import (
    ATTR_STATE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import EventBus, HomeAssistant, ServiceRegistry, StateMachine, SupportsResponse, callback
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.issue_registry import IssueRegistry
from pytest_httpserver import HTTPServer

from custom_components.supernotify import (
    CONF_METHOD,
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.snoozer import Snoozer


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
def mock_hass() -> HomeAssistant:
    hass = Mock(spec=MockableHomeAssistant)
    hass.states = Mock(StateMachine)
    hass.services = Mock(ServiceRegistry)
    hass.config.internal_url = "http://127.0.0.1:28123"
    hass.config.external_url = "https://my.home"
    hass.data = {}
    hass.data["device_registry"] = Mock(spec=DeviceRegistry)
    hass.data["entity_registry"] = Mock(spec=EntityRegistry)
    hass.data["issue_registry"] = Mock(spec=IssueRegistry)
    hass.config_entries._entries = {}
    hass.config_entries._domain_index = {}
    return hass


@pytest.fixture
def mock_context(mock_hass: HomeAssistant) -> Context:
    context = Mock(spec=Context)
    context.hass = mock_hass
    context.scenarios = {}
    context.deliveries = {"chime": {}, "gmail": {CONF_METHOD: "email"}}
    context.cameras = {}
    context.snoozer = Snoozer()
    context.delivery_by_scenario = {}
    context.mobile_actions = {}
    context.content_scenario_templates = {}
    context.hass_internal_url = "http://hass-dev"
    context.hass_external_url = "http://hass-dev.nabu.casa"
    context.media_path = Path("/nosuchpath")
    context.template_path = Path("/templates_here")
    context.people = {
        "person.new_home_owner": {CONF_PERSON: "person.new_home_owner"},
        "person.bidey_in": {
            CONF_PERSON: "person.bidey_in",
            CONF_MOBILE_DEVICES: [{CONF_NOTIFY_ACTION: "mobile_app_iphone"}, {CONF_NOTIFY_ACTION: "mobile_app_nophone"}],
        },
    }
    context.people_state.return_value = [
        {CONF_PERSON: "person.new_home_owner", ATTR_STATE: "not_home"},
        {CONF_PERSON: "person.bidey_in", ATTR_STATE: "home"},
    ]
    context.determine_occupancy.return_value = {
        STATE_HOME: [{CONF_PERSON: "person.bidey_in"}],
        STATE_NOT_HOME: [{CONF_PERSON: "person.new_home_owner"}],
    }

    return context


@pytest.fixture
def mock_notify(hass: HomeAssistant) -> MockAction:
    mock_action: MockAction = MockAction()
    hass.services.async_register(DOMAIN, "mock", mock_action, supports_response=SupportsResponse.NONE)  # type: ignore
    return mock_action


@pytest.fixture
def mock_scenario() -> AsyncMock:
    mock_scenario = AsyncMock()
    mock_scenario.name = "mockery"
    mock_scenario.media = []
    return mock_scenario


@pytest.fixture
async def superconfig() -> Context:
    context = Context()
    await context.initialize()
    return context


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
