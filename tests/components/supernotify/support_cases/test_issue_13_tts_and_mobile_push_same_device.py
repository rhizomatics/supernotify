"""Regression test for GitHub issue #13 - TTS (Android companion app voice announcement)
and mobile push both targeting the same device in one notification.

`tts` declares `ATTR_MOBILE_APP_ID` in its `other_target_categories` (transports/tts.py),
not `unique_target_categories` - deliberately, so it never competes with `mobile_push` for
auto-selection off a bare mobile_app_id (see transport.py's target-driven implicit
selection design and test_target_driven_selection.py's transport uniqueness self-check).
That classification is what keeps this working: `mobile_push` auto-selects normally, and
`tts` can still be explicitly asked to speak on the very same device, without either being
starved of the target or the two colliding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.supernotify.const import CONF_MOBILE_DISCOVERY, CONF_PERSON
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from custom_components.supernotify.transports.tts import TTSTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.common import CallRecord


async def test_tts_and_mobile_push_both_deliver_to_the_same_device(hass: HomeAssistant) -> None:
    """https://github.com/rhizomatics/supernotify/issues/13"""
    hass.services.async_register("tts", "speak", lambda call: None)
    # tts.is_viable() also requires at least one media_player entity to exist anywhere - not
    # used as a target in this test, which is entirely about the mobile_app_id path
    hass.states.async_set("media_player.unrelated_speaker", "idle")
    ctx = TestingContext(homeassistant=hass, viable_transport_types=[MobilePushTransport, TTSTransport])
    register_mobile_app(ctx.hass_api, device_name="pixel", manufacturer="Google", os_name="Android")
    await ctx.test_initialize()

    n = Notification(ctx, "testing 123", target=["mobile_app_pixel"], action_data={"delivery": {"tts": {}}})
    await n.initialize()
    await n.deliver()

    # mobile_push auto-selects off the mobile_app_id target (unique category); tts only
    # fires because it was explicitly named - it never auto-selects off mobile_app_id
    assert "mobile_push" in n.selected_deliveries
    assert "tts" in n.selected_deliveries

    push_calls: list[CallRecord] = n.deliveries["mobile_push"][EnvelopeOutcome.SUCCESS][0].calls  # type: ignore
    tts_calls: list[CallRecord] = n.deliveries["tts"][EnvelopeOutcome.SUCCESS][0].calls  # type: ignore
    assert len(push_calls) == 1
    assert len(tts_calls) == 1

    # both reach the same underlying notify service for this device ...
    assert push_calls[0].domain == "notify"
    assert push_calls[0].action == "mobile_app_pixel"
    assert tts_calls[0].domain == "notify"
    assert tts_calls[0].action == "mobile_app_pixel"

    # ... but with distinct payloads - a normal push notification, and an Android TTS
    # announcement via the companion app's own `tts_text` data key
    tts_action_data = tts_calls[0].action_data or {}
    push_action_data = push_calls[0].action_data or {}
    assert tts_action_data.get("data", {}).get("tts_text") == "testing 123"
    assert "tts_text" not in push_action_data.get("data", {})


async def test_tts_and_mobile_push_both_deliver_to_the_same_device_via_device_discovery(hass: HomeAssistant) -> None:
    """Same as above, but with no target on the call at all - `tts` finds the device itself
    via its own `device_discovery` option (baked into the delivery's own fixed target at
    startup, see Delivery.discover_devices()), and `mobile_push` finds it the usual way, via
    the recipient's own mobile-discovered device - two independent auto-resolution paths
    converging on the same device, neither one starving the other."""
    hass.services.async_register("tts", "speak", lambda call: None)
    hass.states.async_set("media_player.unrelated_speaker", "idle")
    ctx = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.test_user", CONF_MOBILE_DISCOVERY: True}],
        transports={"tts": {"delivery_defaults": {"options": {"device_discovery": True}}}},
        viable_transport_types=[MobilePushTransport, TTSTransport],
    )
    register_mobile_app(ctx.hass_api, device_name="pixel", manufacturer="Google", os_name="Android")
    await ctx.test_initialize()

    n = Notification(ctx, "testing 123", action_data={"delivery": {"tts": {}}})
    await n.initialize()
    await n.deliver()

    assert "mobile_push" in n.selected_deliveries
    assert "tts" in n.selected_deliveries

    push_calls: list[CallRecord] = n.deliveries["mobile_push"][EnvelopeOutcome.SUCCESS][0].calls  # type: ignore
    tts_calls: list[CallRecord] = n.deliveries["tts"][EnvelopeOutcome.SUCCESS][0].calls  # type: ignore
    assert len(push_calls) == 1
    assert len(tts_calls) == 1

    assert push_calls[0].domain == "notify"
    assert push_calls[0].action == "mobile_app_pixel"
    assert tts_calls[0].domain == "notify"
    assert tts_calls[0].action == "mobile_app_pixel"

    tts_action_data = tts_calls[0].action_data or {}
    push_action_data = push_calls[0].action_data or {}
    assert tts_action_data.get("data", {}).get("tts_text") == "testing 123"
    assert "tts_text" not in push_action_data.get("data", {})
