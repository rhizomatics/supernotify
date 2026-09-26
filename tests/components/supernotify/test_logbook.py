"""Logbook descriptions, so each notification shows against what caused it"""

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock

from homeassistant.core import HomeAssistant

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import EVENT_NOTIFICATION
from custom_components.supernotify.logbook import async_describe_events


def _describer(hass: HomeAssistant) -> Callable[[Any], dict[str, Any]]:
    registered: dict[str, Any] = {}

    def describe_event(domain: str, event_type: str, describer: Callable[[Any], dict[str, Any]]) -> None:
        registered[event_type] = (domain, describer)

    async_describe_events(hass, describe_event)
    domain, describer = registered[EVENT_NOTIFICATION]
    assert domain == DOMAIN
    return describer


async def test_describes_sent_notification(hass: HomeAssistant) -> None:
    described = _describer(hass)(
        Mock(data={"summary": "Door open", "outcome": "success", "deliveries": ["email", "mobile_push"]})
    )

    assert described == {"name": "SuperNotify", "message": "sent 'Door open' via email, mobile_push"}


async def test_describes_undelivered_notification(hass: HomeAssistant) -> None:
    described = _describer(hass)(Mock(data={"summary": "Door open", "outcome": "dupe", "deliveries": []}))

    assert described["message"] == "skipped duplicate 'Door open'"
