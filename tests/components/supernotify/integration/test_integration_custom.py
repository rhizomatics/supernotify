from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.notify.const import NOTIFY_SERVICE_SCHEMA
from homeassistant.core import Context, SupportsResponse
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import async_setup_component

from conftest import DummyNotificationService
from custom_components.supernotify import DOMAIN
from custom_components.supernotify.hass_api import HomeAssistantAPI
from tests.components.supernotify.doubles_lib import MockCameraEntity
from tests.components.supernotify.hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from conftest import TestImage


async def test_notification_fires_from_event_triggered_automation(
    hass: HomeAssistant, dummy_notify: DummyNotificationService
) -> None:
    """An E2E real Home Assistant automation, triggered by an event, calling supernotify.notify"""
    config = {"delivery": {"dummy": {"transport": "generic", "action": "notify.dummy", "inclusion": ["default"]}}}
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


async def test_context_propagates_to_camera_ptz_and_mobile_push(hass: HomeAssistant, sample_jpeg: TestImage) -> None:
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

    # a real camera entity so the raw image is fetched successfully and cached on the
    # notification - an unavailable camera would leave it uncached and the PTZ move repeated
    camera_entity = MockCameraEntity(sample_jpeg.path)
    await camera_entity.load()
    hass.data["camera"] = Mock(spec=EntityComponent)
    hass.data["camera"].get_entity = Mock(return_value=camera_entity)

    hass.services.async_register("onvif", "ptz", fake_ptz)
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
    config = {"delivery": {"dummy": {"transport": "generic", "action": "notify.dummy", "inclusion": ["default"]}}}
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


async def test_notify_action_group_fans_out_to_members(hass: HomeAssistant) -> None:
    """https://www.home-assistant.io/integrations/group/#notify-action-groups: a legacy
    `notify: - platform: group` service fans a single call out to its member notify services.
    Supernotify needs no group-specific handling for this - the generic transport just calls the
    group's own service name like any other notify action, and Home Assistant does the fan-out."""
    phone_a = DummyNotificationService()
    phone_b = DummyNotificationService()
    for name, service in (("phone_a", phone_a), ("phone_b", phone_b)):
        hass.services.async_register(
            NOTIFY_DOMAIN,
            name,
            service._async_notify_message_service,
            schema=NOTIFY_SERVICE_SCHEMA,
            supports_response=SupportsResponse.NONE,
        )
    assert await async_setup_component(
        hass,
        "notify",
        {
            "notify": [
                {
                    "platform": "group",
                    "name": "Family",
                    "services": [{"action": "phone_a"}, {"action": "phone_b"}],
                }
            ]
        },
    )
    config = {"delivery": {"family": {"transport": "generic", "action": "notify.family", "inclusion": ["default"]}}}
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "notify", {"message": "dinner is ready"}, blocking=True)
    await hass.async_block_till_done()

    for service in (phone_a, phone_b):
        assert len(service.calls) == 1
        message, _title, _target, _kwargs = service.calls[0]
        assert message == "dinner is ready"
