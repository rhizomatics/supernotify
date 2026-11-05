"""Logbook descriptions, so each notification shows against what caused it"""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import async_load_integrations

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import EVENT_NOTIFICATION
from custom_components.supernotify.logbook import async_describe_events


async def _describer(hass: HomeAssistant, language: str = "en") -> Callable[[Any], dict[str, Any]]:
    # as Home Assistant does when it sets the integration up
    hass.config.language = language
    await async_load_integrations(hass, {DOMAIN})
    registered: dict[str, Any] = {}

    def describe_event(domain: str, event_type: str, describer: Callable[[Any], dict[str, Any]]) -> None:
        registered[event_type] = (domain, describer)

    async_describe_events(hass, describe_event)
    domain, describer = registered[EVENT_NOTIFICATION]
    assert domain == DOMAIN
    return describer


async def test_describes_sent_notification(hass: HomeAssistant) -> None:
    described = (await _describer(hass))(
        Mock(data={"summary": "Door open", "outcome": "success", "deliveries": ["email", "mobile_push"]})
    )

    assert described == {
        "name": "Supernotify",
        "message": 'sent "Door open" via email, mobile_push',
        "icon": "mdi:bell-ring-outline",
    }


async def test_describes_undelivered_notification(hass: HomeAssistant) -> None:
    described = (await _describer(hass))(Mock(data={"summary": "Door open", "outcome": "dupe", "deliveries": []}))

    assert described["message"] == 'skipped duplicate "Door open"'


async def test_describes_notification_in_configured_language(hass: HomeAssistant) -> None:
    described = (await _describer(hass, "de"))(Mock(data={"summary": "Door open", "outcome": "dupe", "deliveries": ["email"]}))

    assert described["message"] == 'hat das Duplikat "Door open" übersprungen (über email)'


async def test_describes_unknown_outcome(hass: HomeAssistant) -> None:
    described = (await _describer(hass))(Mock(data={"summary": "Door open", "deliveries": []}))

    assert described["message"] == 'notified "Door open"'
