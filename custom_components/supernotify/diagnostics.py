"""Diagnostics support for the Supernotify integration.

Exposes the same operational state already surfaced piecemeal through the various
`supernotify.enquire_*` admin services (notify.py) - recipients, scenario/delivery routing,
snoozes, the last notification sent, and the sent/failure counters - through Home Assistant's
standard Settings > Devices & Services > Supernotify > Download diagnostics flow, so a bug
report doesn't require walking the user through calling half a dozen services first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import SupernotifyConfigEntry

# Person.as_dict() (people.py) is the source of every identifying field below - reached both
# directly (enquire_recipients) and indirectly (a snooze or the last notification can reference
# a recipient by the same fields). async_redact_data walks every nested dict/list, so listing
# the field names here is enough regardless of where they turn up in the returned structure.
TO_REDACT = {
    "email",
    "phone_number",
    "user_id",
    "alias",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SupernotifyConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    service = entry.runtime_data
    last_notification = service.last_notification

    data: dict[str, Any] = {
        "entry": {
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "counters": {
            "sent": service.sent,
            "failures": service.failures,
        },
        "housekeeping": service.housekeeping,
        "recipients": service.enquire_recipients(),
        "scenarios": service.enquire_scenarios(),
        "deliveries_by_scenario": service.enquire_deliveries_by_scenario(),
        "implicit_deliveries": service.enquire_implicit_deliveries(),
        "snoozes": service.enquire_snoozes(),
        "last_notification": last_notification.contents(diagnostics=True) if last_notification else None,
        "archive_enabled": service.context.archive.enabled,
        "media_storage_configured": bool(service.context.media_storage.media_path),
    }

    return async_redact_data(data, TO_REDACT)
