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


async def _deliver_with_data(delivery_data: dict, target: list[str] | None = None) -> tuple[TestingContext, bool]:
    context = TestingContext(
        deliveries={"speaker": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        hass_external_url="https://myserver",
    )
    uut = MediaPlayerTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()
    envelope = Envelope(
        Delivery("speaker", context.delivery_config("speaker"), uut),
        Notification(context, "hello there", action_data={ATTR_DELIVERY: {"speaker": {CONF_DATA: delivery_data}}}),
        target=Target(target or ["media_player.kitchen_cast"]),
    )
    with patch.object(envelope, "grab_image", AsyncMock()) as grab_image_mock:
        result = await uut.deliver(envelope)
    grab_image_mock.assert_not_awaited()
    return context, result


async def test_notify_media_generic_audio_relative_url_defaults_to_music() -> None:
    """A media_content_id plays arbitrary content (e.g. an mp3), relative URLs absolutised,
    content type defaulting to `music`, and no image grab attempted."""
    context, result = await _deliver_with_data({"media_content_id": "/local/sounds/bell.mp3", "announce": True})
    assert result is True
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "media_player",
        "play_media",
        service_data={
            "media": {"media_content_id": "https://myserver/local/sounds/bell.mp3", "media_content_type": "music"},
            "announce": True,
        },
        target={"entity_id": ["media_player.kitchen_cast"]},
        blocking=False,
        context=None,
        return_response=False,
    )


async def test_notify_media_generic_content_passthrough_with_type_override() -> None:
    """Absolute URLs and media-source ids are passed through untouched, type can be overridden."""
    for content_id in ("http://192.168.1.10:8123/local/alarm.mp3", "media-source://media_source/local/alarm.mp3"):
        context, result = await _deliver_with_data({"media_content_id": content_id, "media_content_type": "audio/mpeg"})
        assert result is True
        context.hass.services.async_call.assert_called_with(  # type: ignore
            "media_player",
            "play_media",
            service_data={"media": {"media_content_id": content_id, "media_content_type": "audio/mpeg"}},
            target={"entity_id": ["media_player.kitchen_cast"]},
            blocking=False,
            context=None,
            return_response=False,
        )


async def test_notify_media_generic_content_takes_priority_over_snapshot() -> None:
    context, result = await _deliver_with_data({
        "media_content_id": "/local/sounds/bell.mp3",
        ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/ftp/pic.jpeg"},
    })
    assert result is True
    call = context.hass.services.async_call.call_args  # type: ignore
    assert call.kwargs["service_data"]["media"]["media_content_id"] == "https://myserver/local/sounds/bell.mp3"
