from homeassistant.const import CONF_ACTION, CONF_DEFAULT

from custom_components.supernotify import CONF_TRANSPORT, TRANSPORT_ALEXA_MEDIA_PLAYER
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_media_player import AlexaMediaPlayerTransport

DELIVERY = {
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
}


async def test_notify_alexa_media_player(mock_hass, mock_people_registry, uninitialized_superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    delivery_config = {
        "override": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_DEFAULT: True, CONF_ACTION: "notify.alexa_media_player"}
    }
    context = uninitialized_superconfig
    context._deliveries = delivery_config

    uut = AlexaMediaPlayerTransport(mock_hass, context, mock_people_registry, delivery_config)
    await uut.initialize()
    context.configure_for_tests(transport_instances=[uut])
    await context.initialize()
    notification = Notification(context, mock_people_registry, message="hello there")
    await notification.initialize()
    await uut.deliver(Envelope("default", notification, target=Target(["media_player.hall", "media_player.toilet"])))
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "alexa_media_player",
        service_data={
            "message": "hello there",
            "data": {"type": "announce"},
            "target": ["media_player.hall", "media_player.toilet"],
        },
    )


def test_alexa_transport_selects_targets(mock_hass, superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    uut = AlexaMediaPlayerTransport(mock_hass, superconfig, {"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER}})
    assert uut.select_targets(Target(["switch.alexa_1", "media_player.hall_1"])).entity_ids == ["media_player.hall_1"]
