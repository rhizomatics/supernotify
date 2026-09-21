"""Custom exceptions for the Supernotify integration."""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from . import DOMAIN


class UncategorizedTargetError(HomeAssistantError):
    """One or more targets on this notification could not be matched to any delivery.

    Raised once, at the end of a notification's delivery, after every target that *could*
    be categorized has already been sent - this only reports the ones that were dropped.
    """

    def __init__(self, delivered_count: int, uncategorized: dict[str, list[str]]) -> None:
        targets = sorted({t for values in uncategorized.values() for t in values})
        deliveries = sorted(uncategorized.keys())
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="uncategorized_target",
            translation_placeholders={
                "delivered_count": str(delivered_count),
                "uncategorized_count": str(len(targets)),
                "uncategorized_targets": ", ".join(targets),
                "deliveries": ", ".join(deliveries),
            },
        )
