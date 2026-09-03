from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from conftest import DummyNotificationService


async def test_notification_fires_from_event_triggered_automation(
    hass: HomeAssistant, dummy_notify: DummyNotificationService
) -> None:
    """A real Home Assistant automation, triggered by an event, calling notify.supernotify -
    the actual path used in practice, rather than a test calling notify.supernotify directly."""
    config = {"delivery": {"dummy": {"transport": "generic", "action": "notify.dummy"}}}
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "notify on doorbell",
                    "trigger": [{"platform": "event", "event_type": "doorbell_pressed"}],
                    "action": [
                        {
                            "action": "notify.supernotify",
                            "data": {"message": "Someone is at the door"},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.bus.async_fire("doorbell_pressed")
    await hass.async_block_till_done()

    assert len(dummy_notify.calls) == 1
    message, _title, _target, _kwargs = dummy_notify.calls[0]
    assert message == "Someone is at the door"
