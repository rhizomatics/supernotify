from typing import TYPE_CHECKING, Any, LiteralString, cast

import pytest
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_httpserver import HTTPServer

from custom_components.supernotify import (
    ATTR_PRIORITY,
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
    CONF_PRIORITY,
    CONF_TRANSPORT,
    DOMAIN,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    TRANSPORT_MOBILE_PUSH,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import QualifiedTargetType, RecipientType, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.snoozer import Snooze
from custom_components.supernotify.transports.mobile_push import MobilePushTransport

if TYPE_CHECKING:
    from custom_components.supernotify.common import CallRecord
from conftest import TestingContext


async def test_on_notify_mobile_push_with_media(uninitialized_unmocked_config: Context, mock_hass: HomeAssistant) -> None:
    """Test on_notify_mobile_push."""
    ctx = TestingContext(deliveries={"media_test": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH}})

    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)
    await uut.deliver(
        Envelope(
            Delivery("media_test", ctx.deliveries["media_test"], uut),
            Notification(
                ctx,
                message="hello there",
                action_data={
                    "media": {
                        "camera_entity_id": "camera.porch",
                        "camera_ptz_preset": "front-door",
                        "clip_url": "http://my.home/clip.mp4",
                    },
                    "actions": [{"action": "URI", "title": "My Camera App", "url": "http://my.home/app1"}],
                },
            ),
            target=Target({"action": ["notify.mobile_app_new_iphone"]}),
        ),
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "mobile_app_new_iphone",
        service_data={
            "message": "hello there",
            "data": {
                "actions": [
                    {"action": "URI", "title": "My Camera App", "url": "http://my.home/app1"},
                    {
                        "action": "SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_camera.porch",
                        "title": "Snooze camera notifications for camera.porch",
                        "behavior": "textInput",
                        "textInputButtonTitle": "Minutes to snooze",
                        "textInputPlaceholder": "60",
                    },
                ],
                "push": {"interruption-level": "active"},
                "group": "general",
                "entity_id": "camera.porch",
                "video": "http://my.home/clip.mp4",
            },
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_on_notify_mobile_push_with_explicit_target() -> None:
    """Test on_notify_mobile_push."""
    ctx = TestingContext(deliveries={"media_test": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH}})
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    await uut.deliver(
        Envelope(
            Delivery("media_test", ctx.deliveries["media_test"], uut),
            Notification(ctx, message="hello there", title="testing"),
            target=Target({"action": ["notify.mobile_app_new_iphone"]}),
        )
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "mobile_app_new_iphone",
        service_data={
            "title": "testing",
            "message": "hello there",
            "data": {"push": {"interruption-level": "active"}, "group": "general"},
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_on_notify_mobile_push_with_person_derived_targets() -> None:
    """Test on_notify_mobile_push."""
    ctx = TestingContext(
        recipients=[{"person": "person.test_user", "mobile_devices": [{"notify_action": "mobile_app_test_user_iphone"}]}]
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    n = Notification(ctx, message="hello there", title="testing")
    await n.initialize()
    uut = MobilePushTransport(ctx)
    recipients: list[Target] = n.generate_recipients("dummy", uut)
    assert len(recipients) == 1
    assert len(recipients[0].actions) == 1
    assert recipients[0].actions[0] == "mobile_app_test_user_iphone"


async def test_on_notify_mobile_push_with_critical_priority() -> None:
    """Test on_notify_mobile_push."""
    ctx = TestingContext(
        recipients=[{"person": "person.test_user", "mobile_devices": [{"notify_action": "mobile_app_test_user_iphone"}]}],
        deliveries={"default": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH}},
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    await uut.deliver(
        Envelope(
            Delivery("default", ctx.deliveries["default"], uut),
            Notification(
                ctx,
                message="hello there",
                title="testing",
                action_data={CONF_PRIORITY: PRIORITY_CRITICAL},
            ),
            target=Target({"action": ["notify.mobile_app_test_user_iphone"]}),
        )
    )
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "mobile_app_test_user_iphone",
        service_data={
            "title": "testing",
            "message": "hello there",
            "data": {
                "push": {"interruption-level": "critical", "sound": {"name": "default", "critical": 1, "volume": 1.0}},
            },
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


@pytest.mark.parametrize("priority", PRIORITY_VALUES)
async def test_priority_interpretation(mock_hass: HomeAssistant, unmocked_config: Context, priority: LiteralString) -> None:
    priority_map = {
        PRIORITY_CRITICAL: "critical",
        PRIORITY_HIGH: "time-sensitive",
        PRIORITY_LOW: "passive",
        PRIORITY_MEDIUM: "active",
    }
    context = unmocked_config
    delivery_config = {"default": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH}}
    uut = MobilePushTransport(context)
    context.configure_for_tests([uut])
    await context.initialize()
    e: Envelope = Envelope(
        Delivery("default", delivery_config["default"], uut),
        Notification(context, message="hello there", title="testing", action_data={ATTR_PRIORITY: priority}),
        target=Target({"action": ["mobile_app_test_user_iphone"]}),
    )
    await uut.deliver(e)
    call: CallRecord = e.calls[0]
    assert call.action_data is not None
    assert "data" in call.action_data
    assert call.action_data["data"]["push"]["interruption-level"] == priority_map.get(priority, "active")


INTEGRATION_CONFIG = {
    "name": DOMAIN,
    "platform": DOMAIN,
    "delivery": {
        "push": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH},
    },
    "recipients": [{"person": "person.house_owner", "mobile_devices": {"notify_action": "notify.mobile_app_new_iphone"}}],
}


async def test_top_level_data_used(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, NOTIFY_DOMAIN, config={NOTIFY_DOMAIN: [INTEGRATION_CONFIG]})
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        {
            "title": "my title",
            "message": "integration ttldu",
            "data": {"priority": "low", "clickAction": "android_something", "transparency": 50},
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    notification: dict[str, Any] = cast(
        "dict[str, Any]",
        await hass.services.async_call("supernotify", "enquire_last_notification", None, blocking=True, return_response=True),
    )
    assert notification is not None
    # no android integration in test env
    assert "undelivered_envelopes" in notification
    assert notification["undelivered_envelopes"][0]["data"]["clickAction"] == "android_something"


async def test_action_title(mock_hass: HomeAssistant, unmocked_config: Context, local_server: HTTPServer) -> None:
    uut = MobilePushTransport(unmocked_config)
    action_url = local_server.url_for("/action_goes_here")
    local_server.expect_oneshot_request("/action_goes_here").respond_with_data(
        "<html><title>my old action page</title><html>", content_type="text/html"
    )

    assert await uut.action_title(action_url) == "my old action page"
    # cached response
    assert await uut.action_title(action_url) == "my old action page"

    assert await uut.action_title("http://127.0.0.1/no/such/page") is None


async def test_on_notify_mobile_push_with_broken_mobile_targets() -> None:
    """Test on_notify_mobile_push."""
    ctx = TestingContext(
        recipients=[
            {
                CONF_PERSON: "person.bidey_in",
                ATTR_STATE: "home",
                CONF_MOBILE_DEVICES: [{CONF_NOTIFY_ACTION: "mobile_app_iphone"}, {CONF_NOTIFY_ACTION: "mobile_app_nophone"}],
            },
        ]
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    e = Envelope(
        Delivery("", {}, uut),
        Notification(ctx, message="hello there", title="testing"),
        target=Target({"action": ["mobile_app_nophone"]}),
    )
    assert ctx.hass is not None
    assert ctx.hass.services is not None
    ctx.hass.services.async_call.side_effect = Exception(  # type: ignore
        "Boom!"
    )
    await uut.deliver(e)
    expected_snooze = Snooze(QualifiedTargetType.ACTION, RecipientType.USER, "mobile_app_nophone", "person.bidey_in")
    assert ctx.snoozer.snoozes == {"ACTION_mobile_app_nophone_person.bidey_in": expected_snooze}
    assert ctx.snoozer.current_snoozes() == [expected_snooze]
