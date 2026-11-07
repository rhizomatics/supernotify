"""The house the Docker preview is seeded as (see preview/seed.py), so what's seen there is what's
tested here"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .framework import House


async def test_configured_from_the_demo_integration(hass: HomeAssistant, preview_house: House) -> None:
    context = hass.config_entries.async_entries("supernotify")[0].runtime_data.context
    assert sorted(context.delivery_registry.deliveries) == ["chime_siren_all", "media", "notify_entity", "persistent", "tts"]
    assert sorted(context.people_registry.people) == ["person.alice", "person.bob"]


async def test_notify_no_targets_reaches_no_one(hass: HomeAssistant, preview_house: House) -> None:
    """Neither person has a mobile app, e-mail address or phone number to be reached on"""
    await preview_house.assert_e2e(
        """
        message: Tea's up
    """,
        expected_calls={},
        expected_entities={},
    )


async def test_notify_demo_notify_entity(hass: HomeAssistant, preview_house: House) -> None:
    await preview_house.assert_e2e(
        """
        message: Tea's up
        target: notify.notifier
    """,
        expected_calls={"notify": ["send_message"]},
        expected_entities={"notify": ["notify.notifier"]},
    )
