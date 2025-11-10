from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME

from custom_components.supernotify import CONF_DATA, CONF_DELIVERY, CONF_TRANSPORT, TRANSPORT_NOTIFY_ENTITY
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
    )


async def test_target_selection() -> None:
    ctx = TestingContext(transport_types=[NotifyEntityTransport])
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NOTIFY_ENTITY)

    assert uut.select_targets(Target(["notify.pong", "weird_generic_a", "notify"])).entity_ids == ["notify.pong"]
