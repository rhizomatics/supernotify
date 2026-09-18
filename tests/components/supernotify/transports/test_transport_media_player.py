from pathlib import Path
from unittest.mock import AsyncMock, patch

from custom_components.supernotify.const import (
    ATTR_DELIVERY,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    CONF_DATA,
    CONF_TRANSPORT,
    TRANSPORT_MEDIA,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.media_player import MediaPlayerTransport
from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_notify_media_image() -> None:
    """Test on_notify_alexa."""
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )

    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    uut = MediaPlayerTransport(context)

    await uut.deliver(
        Envelope(
            Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
            Notification(
                context,
                "hello there",
                action_data={
                    ATTR_DELIVERY: {"alexa_show": {CONF_DATA: {ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/ftp/pic.jpeg"}}}}
                },
            ),
            target=Target(["media_player.echo_show_8", "media_player.echo_show_10"]),
        )
    )

    context.hass.services.async_call.assert_called_with(  # type: ignore
        "media_player",
        "play_media",
        service_data={"media": {"media_content_id": "https://myserver/ftp/pic.jpeg", "media_content_type": "image"}},
        target={"entity_id": ["media_player.echo_show_8", "media_player.echo_show_10"]},
        blocking=False,
        context=None,
        return_response=False,
    )


async def test_notify_media_no_targets() -> None:
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    result = await uut.deliver(
        Envelope(
            Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
            Notification(context, "hello there"),
            target=Target([]),
        )
    )
    assert result is False


async def test_notify_media_falls_back_to_grab_image() -> None:
    """Regression test: media_player previously ignored delivery-specific `jpeg_opts`/
    `png_opts`/`reprocess` options entirely, since it only ever looked at an explicit
    snapshot_url and never called envelope.grab_image(). It now falls back to
    grab_image() + media_storage.object_url() when no explicit snapshot_url is given,
    so those options take effect here too, same as the other image-attaching transports."""
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    envelope = Envelope(
        Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
        Notification(context, "hello there"),
        target=Target(["media_player.echo_show_8"]),
    )

    with (
        patch.object(envelope, "grab_image", AsyncMock(return_value=Path("/media/supernotify/snapshot.jpg"))),
        patch.object(context.media_storage, "object_url", AsyncMock(return_value="https://myserver/media/snapshot.jpg")),
    ):
        result = await uut.deliver(envelope)

    assert result is True
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "media_player",
        "play_media",
        service_data={"media": {"media_content_id": "https://myserver/media/snapshot.jpg", "media_content_type": "image"}},
        target={"entity_id": ["media_player.echo_show_8"]},
        blocking=False,
        context=None,
        return_response=False,
    )


async def test_notify_media_explicit_snapshot_url_skips_grab_image() -> None:
    """An explicit snapshot_url still takes priority and short-circuits grab_image()."""
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    envelope = Envelope(
        Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
        Notification(
            context,
            "hello there",
            action_data={ATTR_DELIVERY: {"alexa_show": {CONF_DATA: {ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/ftp/pic.jpeg"}}}}},
        ),
        target=Target(["media_player.echo_show_8"]),
    )

    with patch.object(envelope, "grab_image", AsyncMock()) as grab_image_mock:
        result = await uut.deliver(envelope)

    assert result is True
    grab_image_mock.assert_not_awaited()


async def test_notify_media_no_snapshot_url() -> None:
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    result = await uut.deliver(
        Envelope(
            Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
            Notification(context, "hello there"),
            target=Target(["media_player.echo_show_8"]),
        )
    )
    assert result is False


async def test_notify_media_image_with_announce_and_enqueue() -> None:
    context = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("alexa_show", context.delivery_config("alexa_show"), uut),
            Notification(
                context,
                "hello there",
                action_data={
                    ATTR_DELIVERY: {
                        "alexa_show": {
                            CONF_DATA: {
                                ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/ftp/pic.jpeg"},
                                "announce": True,
                                "enqueue": "add",
                            }
                        }
                    }
                },
            ),
            target=Target(["media_player.echo_show_8"]),
        )
    )

    context.hass.services.async_call.assert_called_with(  # type: ignore
        "media_player",
        "play_media",
        service_data={
            "media": {"media_content_id": "https://myserver/ftp/pic.jpeg", "media_content_type": "image"},
            "announce": True,
            "enqueue": "add",
        },
        target={"entity_id": ["media_player.echo_show_8"]},
        blocking=False,
        context=None,
        return_response=False,
    )
