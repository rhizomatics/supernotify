from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .framework import House


async def test_notify_no_targets(hass: HomeAssistant, starter_flat: House) -> None:
    await starter_flat.assert_e2e(
        """
        message: Tea's up
    """,
        expected_calls={"notify": ["mobile_app_jo_phone"]},
        expected_entities={},
    )


async def test_notify_email_target_does_nothing(hass: HomeAssistant, starter_flat: House) -> None:
    await starter_flat.assert_e2e(
        """
                message: Tea's up
                target:
                  - jo@house.org
            """,
        expected_calls=None,
        expected_entities=None,
    )
