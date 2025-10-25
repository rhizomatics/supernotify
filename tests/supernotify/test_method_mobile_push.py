from typing import TYPE_CHECKING, Any, LiteralString, cast

import pytest
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_httpserver import HTTPServer

from custom_components.supernotify import (
    ATTR_PRIORITY,
    CONF_METHOD,
    CONF_PRIORITY,
    DOMAIN,
    METHOD_MOBILE_PUSH,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    QualifiedTargetType,
    RecipientType,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.mobile_push import MobilePushDeliveryMethod
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.snoozer import Snooze

if TYPE_CHECKING:
    from custom_components.supernotify.common import CallRecord


async def test_on_notify_mobile_push_with_media(mock_hass: HomeAssistant) -> None:
    """Test on_notify_mobile_push."""
    context = Context()
    await context.initialize()
    uut = MobilePushDeliveryMethod(mock_hass, context, {"media_test": {CONF_METHOD: METHOD_MOBILE_PUSH}})
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "media_test",
            Notification(
                context,
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
            targets=["mobile_app_new_iphone"],
        ),
    )
    mock_hass.services.async_call.assert_called_with(  # type: ignore
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
    )


async def test_on_notify_mobile_push_with_explicit_target(mock_hass: HomeAssistant) -> None:
    """Test on_notify_mobile_push."""
    context = Context()
    await context.initialize()
    uut = MobilePushDeliveryMethod(mock_hass, context, {"media_test": {CONF_METHOD: METHOD_MOBILE_PUSH}})
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope("media_test", Notification(context, message="hello there", title="testing"), targets=["mobile_app_new_iphone"])
    )
    mock_hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "mobile_app_new_iphone",
        service_data={
            "title": "testing",
            "message": "hello there",
            "data": {"push": {"interruption-level": "active"}, "group": "general"},
        },
    )


async def test_on_notify_mobile_push_with_person_derived_targets(mock_hass: HomeAssistant) -> None:
    """Test on_notify_mobile_push."""
    context = Context(
        recipients=[{"person": "person.test_user", "mobile_devices": [{"notify_action": "mobile_app_test_user_iphone"}]}]
    )
    await context.initialize()
    n = Notification(context, message="hello there", title="testing")
    uut = MobilePushDeliveryMethod(mock_hass, context, {})
    recipients: list[dict[str, Any]] = n.generate_recipients("dummy", uut)
    assert len(recipients) == 1
    assert recipients[0]["person"] == "person.test_user"
    assert recipients[0]["mobile_devices"][0]["notify_action"] == "mobile_app_test_user_iphone"


async def test_on_notify_mobile_push_with_critical_priority(mock_hass: HomeAssistant) -> None:
    """Test on_notify_mobile_push."""
    context = Context(
        recipients=[{"person": "person.test_user", "mobile_devices": [{"notify_action": "mobile_app_test_user_iphone"}]}]
    )
    await context.initialize()
    uut = MobilePushDeliveryMethod(mock_hass, context, {"default": {CONF_METHOD: METHOD_MOBILE_PUSH}})
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()
    await uut.deliver(
        Envelope(
            "default",
            Notification(context, message="hello there", title="testing", action_data={CONF_PRIORITY: PRIORITY_CRITICAL}),
            targets=["mobile_app_test_user_iphone"],
        )
    )
    mock_hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "mobile_app_test_user_iphone",
        service_data={
            "title": "testing",
            "message": "hello there",
            "data": {
                "push": {"interruption-level": "critical", "sound": {"name": "default", "critical": 1, "volume": 1.0}},
            },
        },
    )


@pytest.mark.parametrize("priority", PRIORITY_VALUES)
async def test_priority_interpretation(mock_hass: HomeAssistant, priority: LiteralString) -> None:
    priority_map = {
        PRIORITY_CRITICAL: "critical",
        PRIORITY_HIGH: "time-sensitive",
        PRIORITY_LOW: "passive",
        PRIORITY_MEDIUM: "active",
    }
    context = Context()
    await context.initialize()
    uut = MobilePushDeliveryMethod(mock_hass, context, {"default": {CONF_METHOD: METHOD_MOBILE_PUSH}})
    context.configure_for_tests([uut])
    await context.initialize()
    e: Envelope = Envelope(
        "default",
        Notification(context, message="hello there", title="testing", action_data={ATTR_PRIORITY: priority}),
        targets=["mobile_app_test_user_iphone"],
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
        "push": {CONF_METHOD: METHOD_MOBILE_PUSH},
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
    assert "undelivered_envelopes" in notification  # no android integration in test env
    assert notification["undelivered_envelopes"][0]["data"]["clickAction"] == "android_something"


async def test_action_title(mock_hass: HomeAssistant, superconfig: Context, local_server: HTTPServer) -> None:
    uut = MobilePushDeliveryMethod(mock_hass, superconfig, {})
    action_url = local_server.url_for("/action_goes_here")
    local_server.expect_oneshot_request("/action_goes_here").respond_with_data(
        "<html><title>my old action page</title><html>", content_type="text/html"
    )

    assert await uut.action_title(action_url) == "my old action page"
    # cached response
    assert await uut.action_title(action_url) == "my old action page"

    assert await uut.action_title("http://127.0.0.1/no/such/page") is None


async def test_on_notify_mobile_push_with_broken_mobile_targets(mock_context: Context) -> None:
    """Test on_notify_mobile_push."""
    uut = MobilePushDeliveryMethod(mock_context.hass, mock_context, {})
    e = Envelope(
        "",
        Notification(mock_context, message="hello there", title="testing"),
        targets=["mobile_app_nophone"],
    )
    assert mock_context.hass is not None
    assert mock_context.hass.services is not None
    mock_context.hass.services.async_call.side_effect = Exception("Boom!")  # type: ignore
    await uut.deliver(e)
    expected_snooze = Snooze(QualifiedTargetType.ACTION, RecipientType.USER, "mobile_app_nophone", "person.bidey_in")
    assert mock_context.snoozer.snoozes == {"ACTION_mobile_app_nophone_person.bidey_in": expected_snooze}
    assert mock_context.snoozer.current_snoozes() == [expected_snooze]
