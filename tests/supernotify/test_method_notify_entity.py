from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME

from custom_components.supernotify import CONF_DATA, CONF_DELIVERY, CONF_TRANSPORT, TRANSPORT_NOTIFY_ENTITY
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport


async def test_deliver(mock_hass, mock_people_registry, superconfig) -> None:  # type: ignore
    context = superconfig
    uut = NotifyEntityTransport(
        mock_hass,
        context,
        mock_people_registry,
        {
            "ping": {
                CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY,
                CONF_NAME: "teleport",
            }
        },
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "ping",
            Notification(
                context,
                mock_people_registry,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"teleport": {CONF_DATA: {"cuteness": "not_on_this_transport"}}}},
            ),
            target=Target(["notify.pong", "weird_generic_a"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "send_message",
        service_data={ATTR_MESSAGE: "hello there", ATTR_TITLE: "testing"},
        target={ATTR_ENTITY_ID: ["notify.pong"]},
    )
