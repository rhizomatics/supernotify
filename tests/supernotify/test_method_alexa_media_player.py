from homeassistant.const import CONF_ACTION

from custom_components.supernotify import CONF_TRANSPORT, TRANSPORT_ALEXA_MEDIA_PLAYER
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_media_player import AlexaMediaPlayerTransport

from .hass_setup_lib import TestingContext

DELIVERY = {
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
}


async def test_notify_alexa_media_player(uninitialized_unmocked_config: Context) -> None:
    """Test on_notify_alexa."""
    delivery_config = {
        "override": {
            CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER,
            CONF_ACTION: "notify.alexa_media_player_custom",
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._deliveries = delivery_config

    uut = AlexaMediaPlayerTransport(context)
    await uut.initialize()
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    notification = Notification(context, message="hello there")
    await notification.initialize()
    await uut.deliver(
        Envelope(
            Delivery("override", delivery_config["override"], uut),
            notification,
            target=Target(["media_player.hall", "media_player.toilet"]),
        )
    )
    uninitialized_unmocked_config.hass_api.call_service.assert_called_with(  # type: ignore
        "notify",
        "alexa_media_player_custom",
        service_data={
            "message": "hello there",
            "data": {"type": "announce"},
            "target": ["media_player.hall", "media_player.toilet"],
        },
    )


def test_alexa_transport_selects_targets() -> None:
    """Test on_notify_alexa."""
    context = TestingContext(deliveries={"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER}})
    uut = Delivery("unit_testing", {}, AlexaMediaPlayerTransport(context, {}))

    assert uut.select_targets(Target(["switch.alexa_1", "media_player.hall_1"])).entity_ids == ["media_player.hall_1"]
