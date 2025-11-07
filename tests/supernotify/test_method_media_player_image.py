from homeassistant.const import CONF_DEFAULT, CONF_NAME

from custom_components.supernotify import ATTR_DELIVERY, CONF_DATA, CONF_TRANSPORT, TRANSPORT_MEDIA
from custom_components.supernotify.context import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.media_player_image import MediaPlayerImageTransport


async def test_notify_media_image(mock_hass, mock_people_registry) -> None:  # type: ignore
    """Test on_notify_alexa."""
    context = Context()
    context.hass_external_url = "https://myserver"

    uut = MediaPlayerImageTransport(
        mock_hass,
        context,
        mock_people_registry,
        {"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA, CONF_NAME: "alexa_show", CONF_DEFAULT: True}},
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "alexa_show",
            Notification(
                context,
                mock_people_registry,
                "hello there",
                action_data={ATTR_DELIVERY: {"alexa_show": {CONF_DATA: {"snapshot_url": "/ftp/pic.jpeg"}}}},
            ),
            target=Target(["media_player.echo_show_8", "media_player.echo_show_10"]),
        )
    )

    mock_hass.services.async_call.assert_called_with(
        "media_player",
        "play_media",
        service_data={
            "entity_id": ["media_player.echo_show_8", "media_player.echo_show_10"],
            "media_content_id": "https://myserver/ftp/pic.jpeg",
            "media_content_type": "image",
        },
    )
