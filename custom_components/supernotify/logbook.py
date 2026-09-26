"""Describe SuperNotify's logbook events, so each notification shows against what caused it"""

from collections.abc import Callable
from typing import Any

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME, LazyEventPartialState
from homeassistant.core import HomeAssistant, callback

from . import DOMAIN
from .const import EVENT_NOTIFICATION
from .schema import DeliveryOutcome

OUTCOME_VERBS: dict[str, str] = {
    DeliveryOutcome.SUCCESS: "sent",
    DeliveryOutcome.PARTIAL_DELIVERY: "partly sent",
    DeliveryOutcome.FALLBACK_DELIVERY: "sent by fallback",
    DeliveryOutcome.NO_DELIVERY: "did not send",
    DeliveryOutcome.DUPE: "skipped duplicate",
    DeliveryOutcome.ERROR: "failed to send",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[LazyEventPartialState], dict[str, Any]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_notification(event: LazyEventPartialState) -> dict[str, Any]:
        data = event.data
        message: str = f"{OUTCOME_VERBS.get(data.get('outcome', ''), 'notified')} '{data.get('summary', '')}'"
        if data.get("deliveries"):
            message += f" via {', '.join(data['deliveries'])}"
        return {LOGBOOK_ENTRY_NAME: "SuperNotify", LOGBOOK_ENTRY_MESSAGE: message}

    async_describe_event(DOMAIN, EVENT_NOTIFICATION, async_describe_notification)
