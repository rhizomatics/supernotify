from typing import cast

from custom_components.supernotify import (
    ATTR_RECIPIENTS,
    CONF_DELIVERY_DEFAULTS,
    CONF_MOBILE_DISCOVERY,
    CONF_PERSON,
    CONF_TARGET,
    CONF_TRANSPORT,
)
from custom_components.supernotify.notification import Notification

from .doubles_lib import DummyTransport
from .hass_setup_lib import TestingContext


async def test_default_recipients() -> None:
    context = TestingContext(
        recipients=[
            {CONF_PERSON: "person.new_home_owner", CONF_TARGET: "dummy.1"},
            {CONF_PERSON: "person.old_home_owner", CONF_TARGET: "dummy.2"},
            {CONF_PERSON: "person.bidey_in"},
        ],
        deliveries={"testing": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(context)
    await uut.initialize()
    await uut.deliver()
    dummy: DummyTransport = cast("DummyTransport", context.delivery_registry.transports["dummy"])
    assert dummy.service.calls[0].data["entity_id"] == ["dummy.1", "dummy.2"]


async def test_default_recipients_with_override() -> None:
    context = TestingContext(
        recipients=[
            {CONF_PERSON: "person.new_home_owner", CONF_TARGET: "dummy.1", CONF_MOBILE_DISCOVERY: False},
            {CONF_PERSON: "person.old_home_owner", CONF_TARGET: "dummy.2", CONF_MOBILE_DISCOVERY: False},
            {CONF_PERSON: "person.bidey_in", CONF_MOBILE_DISCOVERY: False},
        ],
        deliveries={"testing": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(context, "testing", action_data={ATTR_RECIPIENTS: ["person.new_home_owner"]})
    await uut.initialize()
    await uut.deliver()
    dummy: DummyTransport = cast("DummyTransport", context.delivery_registry.transports["dummy"])
    assert dummy.service.calls[0].data["entity_id"] == ["dummy.1"]


async def test_delivery_override_transport() -> None:
    context = TestingContext(
        deliveries={
            "quiet_alert": {
                "transport": "dummy",
                "target": ["switch.pillow_vibrate"],
                "selection": "explicit",
            },
            "regular_alert": {"transport": "dummy", "target": ["switch.pillow_vibrate"], "selection": ["explicit"]},
            "day_alert": {"transport": "dummy", "selection": ["explicit"]},
        },
        transport_configs={"dummy": {CONF_DELIVERY_DEFAULTS: {"target": ["media_player.hall"]}}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(
        context,
        "testing explicit target in notification call",
        action_data={"delivery": ["regular_alert"]},
        target=["switch.gong"],
    )
    await uut.initialize()
    await uut.deliver()
    envelope = uut.delivered_envelopes["dummy"][0]
    assert envelope.target.entity_ids == ["switch.gong"]

    uut = Notification(context, "testing target specified in delivery config", action_data={"delivery": ["quiet_alert"]})
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes["dummy"][0]
    assert envelope.target.entity_ids == ["switch.pillow_vibrate"]

    uut = Notification(context, "testing defaulting to transport defaults", action_data={"delivery": ["day_alert"]})
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes["dummy"][0]
    assert envelope.target.entity_ids == ["media_player.hall"]
