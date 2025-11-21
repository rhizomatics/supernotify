from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME

from custom_components.supernotify import (
    CONF_ACTION,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_OPTIONS,
    CONF_TRANSPORT,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    TRANSPORT_GENERIC,
    TRANSPORT_NOTIFY_ENTITY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport

from .hass_setup_lib import TestingContext


async def test_deliver(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config
    delivery_config = {
        "ping": {
            CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY,
            CONF_NAME: "teleport",
        }
    }
    uut = NotifyEntityTransport(context)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            Delivery("ping", delivery_config["ping"], uut),
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"teleport": {CONF_DATA: {"cuteness": "not_on_this_transport"}}}},
            ),
            target=Target(["notify.pong", "weird_generic_a"]),
        )
    )
    context.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={ATTR_MESSAGE: "hello there", ATTR_TITLE: "testing"},
        target_data={ATTR_ENTITY_ID: ["notify.pong"]},
        debug=False,
    )


async def test_selects_group_targets() -> None:
    pass
    # TODO: write when groups handled


async def test_doesnt_double_deliver() -> None:
    context = TestingContext(
        deliveries={
            "custom": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "notify.custom",
                CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID], OPTION_TARGET_INCLUDE_RE: [r".*(2|3)"]},
            }
        },
    )

    await context.test_initialize()

    notification = Notification(
        context,
        message="only once please",
        target=["notify.entity_1", "notify.entity_2", "notify.entity_3"],
    )
    await notification.initialize()
    await notification.deliver()
    assert notification.selected_delivery_names == ["custom", "DEFAULT_notify_entity"]

    assert len(notification.delivered_envelopes) == 2

    assert notification.delivered_envelopes[0].delivery_name == "custom"
    assert notification.delivered_envelopes[0].target.entity_ids == ["notify.entity_2", "notify.entity_3"]

    assert notification.delivered_envelopes[1].delivery_name == "DEFAULT_notify_entity"
    assert notification.delivered_envelopes[1].target.entity_ids == ["notify.entity_1"]
