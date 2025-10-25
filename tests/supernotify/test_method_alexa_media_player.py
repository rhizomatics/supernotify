from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_METHOD

from custom_components.supernotify import METHOD_ALEXA_MEDIA_PLAYER
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.alexa_media_player import AlexaMediaPlayerDeliveryMethod
from custom_components.supernotify.notification import Notification

DELIVERY = {
    "alexa_media_player": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
}


async def test_notify_alexa_media_player(mock_hass) -> None:  # type: ignore
    """Test on_notify_alexa."""
    delivery_config = {
        "default": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER, CONF_DEFAULT: True, CONF_ACTION: "notify.alexa_media_player"}
    }
    context = Context(deliveries=delivery_config)
    uut = AlexaMediaPlayerDeliveryMethod(
        mock_hass,
        context,
        delivery_config,
    )
    await uut.initialize()
    context.configure_for_tests(method_instances=[uut])
    await context.initialize()
    await uut.deliver(
        Envelope("default", Notification(context, message="hello there"), targets=["media_player.hall", "media_player.toilet"])
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "alexa_media_player",
        service_data={
            "message": "hello there",
            "data": {"type": "announce"},
            "target": ["media_player.hall", "media_player.toilet"],
        },
    )


def test_alexa_method_selects_targets(mock_hass, superconfig) -> None:  # type: ignore
    """Test on_notify_alexa."""
    uut = AlexaMediaPlayerDeliveryMethod(mock_hass, superconfig, {"announce": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER}})
    assert uut.select_target("switch.alexa_1") is False
    assert uut.select_target("media_player.hall_1") is True
