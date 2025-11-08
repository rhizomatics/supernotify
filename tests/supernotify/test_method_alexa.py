from homeassistant.const import CONF_ACTION, CONF_DEFAULT
from pytest_unordered import unordered

from custom_components.supernotify import CONF_TRANSPORT, TRANSPORT_ALEXA
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_devices import AlexaDevicesTransport

DELIVERY = {
    "alexa_devices": {CONF_TRANSPORT: TRANSPORT_ALEXA, CONF_ACTION: "notify.send_message"},
}


async def test_notify_alexa(mock_hass, mock_people_registry, superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    context = superconfig
    delivery_config = {"default": {CONF_TRANSPORT: TRANSPORT_ALEXA, CONF_DEFAULT: True}}
    uut = AlexaDevicesTransport(mock_hass, context, delivery_config)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    await uut.deliver(
        Envelope(
            "default",
            Notification(context, mock_people_registry, message="hello there"),
            target=Target(["notify.bedroom_echo_announce"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "hello there"},
        target={
            "entity_id": ["notify.bedroom_echo_announce"],
        },
    )


def test_alexa_transport_selects_targets(mock_hass, superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    uut = AlexaDevicesTransport(mock_hass, superconfig, {"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA}})
    assert uut.select_targets(
        Target([
            "switch.alexa_1",
            "media_player.hall_1",
            "notify.bedroom_echo_announce",
            "notify.living_room_echo_2_speak",
            "notify.kitchen_echo",
            "notify.alexa_media_player_announce",
        ])
    ).entity_ids == unordered([
        "notify.living_room_echo_2_speak",
        "notify.bedroom_echo_announce",
        "notify.alexa_media_player_announce",
    ])
