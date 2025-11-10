from homeassistant.const import CONF_NAME

from custom_components.supernotify import ATTR_DELIVERY, CONF_DATA, CONF_TRANSPORT, TRANSPORT_MEDIA
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.media_player_image import MediaPlayerImageTransport

from .hass_setup_lib import TestingContext


async def test_notify_media_image() -> None:
    """Test on_notify_alexa."""
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA, CONF_NAME: "alexa_show"}},
        hass_external_url="https://myserver",
    )

    uut = MediaPlayerImageTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    uut = MediaPlayerImageTransport(context)

    await uut.deliver(
        Envelope(
            Delivery("alexa_show", context.deliveries["alexa_show"], uut),
            Notification(
                context,
                "hello there",
                action_data={ATTR_DELIVERY: {"alexa_show": {CONF_DATA: {"snapshot_url": "/ftp/pic.jpeg"}}}},
            ),
            target=Target(["media_player.echo_show_8", "media_player.echo_show_10"]),
        )
    )

    context.hass.services.async_call.assert_called_with(  # type: ignore
        "media_player",
        "play_media",
        service_data={
            "entity_id": ["media_player.echo_show_8", "media_player.echo_show_10"],
            "media_content_id": "https://myserver/ftp/pic.jpeg",
            "media_content_type": "image",
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
