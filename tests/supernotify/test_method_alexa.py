from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_METHOD
from pytest_unordered import unordered

from custom_components.supernotify import METHOD_ALEXA
from custom_components.supernotify.context import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.alexa_devices import AlexaDevicesDeliveryMethod
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification

DELIVERY = {
    "alexa_devices": {CONF_METHOD: METHOD_ALEXA, CONF_ACTION: "notify.send_message"},
}


async def test_notify_alexa(mock_hass, mock_people_registry) -> None:  # type: ignore
    """Test on_notify_alexa."""
    context = Context()
    delivery_config = {"default": {CONF_METHOD: METHOD_ALEXA, CONF_DEFAULT: True}}
    uut = AlexaDevicesDeliveryMethod(mock_hass, context, delivery_config)
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


def test_alexa_method_selects_targets(mock_hass, superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    uut = AlexaDevicesDeliveryMethod(mock_hass, superconfig, {"announce": {CONF_METHOD: METHOD_ALEXA}})
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
