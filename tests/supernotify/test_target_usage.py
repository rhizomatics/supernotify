from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.generic import GenericTransport

from .hass_setup_lib import TestingContext


async def target_usage_fixture(usage: str) -> TestingContext:
    context = TestingContext(
        deliveries={
            "merge_default_delivery": {
                "transport": "generic",
                "action": "notify.everything",
                "target": ["switch.pillow_vibrate"],
                "target_required": True,
                "target_usage": usage,
            }
        },
        transport_types=[GenericTransport],
    )
    await context.test_initialize()
    return context


async def test_target_use_merge_on_delivery():
    context = await target_usage_fixture("merge_delivery")

    uut = Notification(
        context,
        "testing",
        target=["switch.gong"],
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.gong", "switch.pillow_vibrate"]

    uut = Notification(context, "testing")
    await uut.initialize()
    await uut.deliver()
    assert len(uut.delivered_envelopes) == 0


async def test_target_use_fixed():
    context = await target_usage_fixture("fixed")

    uut = Notification(
        context,
        "testing",
        target=["switch.gong"],
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]


async def test_target_use_on_no_delivery_targets():
    context = await target_usage_fixture("no_delivery")

    uut = Notification(
        context,
        "testing",
        target=["joey@mctoe.com"],
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]

    uut = Notification(context, "testing")
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]


async def test_target_use_on_no_action_targets():
    context = await target_usage_fixture("no_action")

    uut = Notification(
        context,
        "testing",
        target=["joey@mctoe.com"],
    )
    await uut.initialize()
    await uut.deliver()
    assert len(uut.delivered_envelopes) == 0

    uut = Notification(context, "testing")
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]


async def test_target_use_undefined():
    context = await target_usage_fixture(None)

    uut = Notification(
        context,
        "testing",
        target=["joey@mctoe.com"],
    )
    await uut.initialize()
    await uut.deliver()
    assert len(uut.delivered_envelopes) == 0

    uut = Notification(context, "testing")
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]


async def test_target_use_merge_always():
    context = await target_usage_fixture("merge_always")

    uut = Notification(context, "testing", target=["switch.gong"])
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.gong", "switch.pillow_vibrate"]

    uut = Notification(context, "testing")
    await uut.initialize()
    await uut.deliver()
    assert uut.delivered_envelopes[0].target.entity_ids == ["switch.pillow_vibrate"]
