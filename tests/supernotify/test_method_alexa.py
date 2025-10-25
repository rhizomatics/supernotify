from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_METHOD

from custom_components.supernotify import METHOD_ALEXA
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.alexa_devices import AlexaDevicesDeliveryMethod
from custom_components.supernotify.notification import Notification

DELIVERY = {
    "alexa_devices": {CONF_METHOD: METHOD_ALEXA, CONF_ACTION: "notify.send_message"},
}


async def test_notify_alexa(mock_hass) -> None:  # type: ignore
    """Test on_notify_alexa."""
    context = Context()
    delivery_config = {"default": {CONF_METHOD: METHOD_ALEXA, CONF_DEFAULT: True}}
    uut = AlexaDevicesDeliveryMethod(mock_hass, context, delivery_config)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    await uut.deliver(
        Envelope("default", Notification(context, message="hello there"), targets=["notify.bedroom_echo_announce"])
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
    assert uut.select_target("switch.alexa_1") is False
    assert uut.select_target("media_player.hall_1") is False
    assert uut.select_target("notify.bedroom_echo_announce") is True
    assert uut.select_target("notify.living_room_echo_2_speak") is True
    assert uut.select_target("notify.kitchen_echo") is False
    assert uut.select_target("notify.alexa_media_player_announce") is True
