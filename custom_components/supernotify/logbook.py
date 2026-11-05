"""Describe SuperNotify's logbook events, so each notification shows against what caused it"""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ICON,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
    LazyEventPartialState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.translation import async_get_cached_translations

from . import DOMAIN
from .const import EVENT_NOTIFICATION
from .schema import DeliveryOutcome


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None],
) -> None:
    """Describe logbook events."""

    def text(key: str, **placeholders: str) -> str:
        # translations were cached when the integration was set up, in the configured language
        full_key: str = f"component.{DOMAIN}.common.{key}"
        template: str | None = async_get_cached_translations(hass, hass.config.language, "common", DOMAIN).get(
            full_key
        ) or async_get_cached_translations(hass, "en", "common", DOMAIN).get(full_key)
        return template.format(**placeholders) if template else key

    @callback
    def async_describe_notification(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        outcome: str = data.get("outcome", "")
        key: str = f"logbook_{outcome}" if outcome in DeliveryOutcome else "logbook_notified"
        message: str = text(key, summary=data.get("summary", ""))
        if data.get("deliveries"):
            message = text("logbook_via", message=message, deliveries=", ".join(data["deliveries"]))
        return {LOGBOOK_ENTRY_NAME: "Supernotify", LOGBOOK_ENTRY_MESSAGE: message, LOGBOOK_ENTRY_ICON: "mdi:bell-ring-outline"}

    async_describe_event(DOMAIN, EVENT_NOTIFICATION, async_describe_notification)
