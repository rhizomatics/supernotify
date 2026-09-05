from __future__ import annotations

from typing import TYPE_CHECKING

import aiofiles
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.hass_api import HomeAssistantAPI

from .hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from conftest import DummyNotificationService


async def test_notification_fires_from_event_triggered_automation(
    hass: HomeAssistant, dummy_notify: DummyNotificationService
) -> None:
    """An E2E real Home Assistant automation, triggered by an event, calling supernotify.notify"""
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
                            "action": "supernotify.notify",
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


async def test_context_propagates_to_camera_ptz_and_mobile_push(hass: HomeAssistant) -> None:
    """An automation-triggered supernotify.notify call must propagate the automation's Context
    all the way down to the individual Home Assistant service calls it fans out to - both the
    camera PTZ movement and the mobile push notification. notify.supernotify can't do this (see
    the 2.3.0 changelog note on Home Assistant's legacy notify platform not forwarding Context),
    which is one of the reasons supernotify.notify exists.
    """
    hass_api = HomeAssistantAPI(hass)
    register_mobile_app(hass_api, device_name="Test iPhone")
    await async_setup_component(hass, "mobile_app", {"mobile_app": {}})

    ptz_calls: list[ServiceCall] = []
    push_calls: list[ServiceCall] = []

    async def fake_ptz(call: ServiceCall) -> None:
        ptz_calls.append(call)

    async def fake_push(call: ServiceCall) -> None:
        push_calls.append(call)

    async def fake_snapshot(call: ServiceCall) -> None:
        # a real snapshot file so the raw image is cached and only fetched once - a failed/
        # unregistered `camera.snapshot` would leave it uncached and the PTZ move repeated
        async with aiofiles.open(call.data["filename"], "wb") as file:
            await file.write(b"fake-jpeg-bytes")

    hass.services.async_register("onvif", "ptz", fake_ptz)
    hass.services.async_register("camera", "snapshot", fake_snapshot)
    hass.services.async_remove("notify", "mobile_app_test_iphone")
    hass.services.async_register("notify", "mobile_app_test_iphone", fake_push)

    config = {
        "delivery": {"push": {"transport": "mobile_push"}},
        "recipients": [{"person": "person.test_user"}],
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "notify on doorbell, with a camera PTZ move",
                    "trigger": [{"platform": "event", "event_type": "doorbell_pressed"}],
                    "action": [
                        {
                            "action": "supernotify.notify",
                            "data": {
                                "message": "Someone is at the door",
                                "media": {
                                    "camera_entity_id": "camera.front_door",
                                    "camera_ptz_preset": "Doorway",
                                    "camera_delay": 0,
                                },
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    event_context = Context()
    hass.bus.async_fire("doorbell_pressed", context=event_context)
    await hass.async_block_till_done()

    assert len(ptz_calls) == 1
    assert len(push_calls) == 1
    # both service calls carry the same automation-run Context, and that Context traces back
    # (via parent_id) to the event that triggered the automation in the first place
    assert ptz_calls[0].context.id == push_calls[0].context.id
    assert ptz_calls[0].context.parent_id == event_context.id
    assert push_calls[0].context.parent_id == event_context.id


async def test_legacy_notification_fires_from_event_triggered_automation(
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
