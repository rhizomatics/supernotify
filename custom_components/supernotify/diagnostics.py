"""Diagnostics support for the Supernotify integration.

Exposes the same operational state already surfaced piecemeal through the various
`supernotify.enquire_*` admin services (notify.py) - recipients, scenario/delivery routing,
snoozes, the last notification sent, and the sent/failure counters - through Home Assistant's
standard Settings > Devices & Services > Supernotify > Download diagnostics flow, so a bug
report doesn't require walking the user through calling half a dozen services first.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.redact import REDACTED, async_redact_data, partial_redact

if TYPE_CHECKING:
    from . import SupernotifyConfigEntry

_partial_redact = partial(partial_redact, unmasked_prefix=2, unmasked_suffix=1)

# Person.as_dict() (people.py) is the source of every identifying field below - reached both
# directly (enquire_recipients) and indirectly (a snooze or the last notification can reference
# a recipient by the same fields). async_redact_data walks every nested dict/list, so listing
# the field names here is enough regardless of where they turn up in the returned structure.
# email/phone_number keep a couple of characters visible, as Target.as_dict() does, so a bug
# report stays identifiable without exposing the whole address/number.
TO_REDACT = {
    "email": _partial_redact,
    "phone_number": _partial_redact,
    "user_id": lambda _value: REDACTED,
    "alias": lambda _value: REDACTED,
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
        # configuration problems, each naming what's wrong and, where there's a choice, what's configured
        "issues": [
            {
                "issue_id": issue.issue_id,
                "translation_key": issue.translation_key,
                "placeholders": issue.translation_placeholders,
                "severity": issue.severity,
            }
            for (domain, _issue_id), issue in ir.async_get(hass).issues.items()
            if domain == entry.domain and issue.active
        ],
    }

    return async_redact_data(data, TO_REDACT)
