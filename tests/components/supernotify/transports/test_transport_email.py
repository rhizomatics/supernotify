from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import anyio
from homeassistant.const import CONF_ACTION, CONF_EMAIL
from homeassistant.setup import async_setup_component

from custom_components.supernotify.const import (
    ATTR_DATA,
    ATTR_DELIVERY,
    ATTR_MEDIA_SNAPSHOT_PATH,
    CONF_PERSON,
    CONF_TEMPLATE,
    CONF_TRANSPORT,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.email import OPTION_PREHEADER_BLANK, OPTION_PREHEADER_LENGTH, EmailTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


async def test_deliver() -> None:
    """Test on_notify_email."""
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"plain_email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    await uut.deliver(
        Envelope(
            Delivery("plain_email", context.delivery_config("plain_email"), uut),
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={ATTR_DELIVERY: {"plain_email": {ATTR_DATA: {"footer": "pytest"}}}},
            ),
            target=Target(["tester1@assert.com"]),
        )
    )
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "smtp",
        service_data={"target": ["tester1@assert.com"], "title": "testing", "message": "hello there\n\npytest"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_with_template(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={
            "test_email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", CONF_TEMPLATE: "minimal_test.html.j2"}
        },
        template_path=Path("tests/components/supernotify/fixtures/templates"),
        services={"notify": ["smtp"]},
    )
    ctx.hass_api.set_state("device_tracker.joey_mctest", "home")
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_EMAIL)

    await uut.deliver(
        Envelope(
            Delivery("test_email", ctx.delivery_config("test_email"), uut),
            Notification(ctx, message="hello there", title="testing"),
            target=Target(["tester9@assert.com"]),
        )
    )
    await ctx.hass.async_block_till_done()
    assert len(ctx.services["notify.smtp"].calls) == 1
    service_call: ServiceCall = ctx.services["notify.smtp"].calls[0]
    assert service_call.data == {
        "target": ["tester9@assert.com"],
        "title": "testing",
        "message": "hello there",
        "data": {"html": "<H1>testing</H1>\n\n<H2>Joey is home</H2>"},
    }


async def test_deliver_with_preformatted_html() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"default": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
    )

    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    notification = Notification(
        context,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={"message_html": "<H3>testing</H3>", "delivery": {"default": {"data": {"footer": ""}}}},
    )
    await notification.initialize()
    await uut.deliver(
        Envelope(
            Delivery("default", context.delivery_config("default"), uut), notification, target=Target(["tester9@assert.com"])
        )
    )
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "smtp",
        service_data={
            "target": ["tester9@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"html": "<H3>testing</H3>"},
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_with_preformatted_html_and_image() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"default": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
    )

    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    notification = Notification(
        context,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={
            "message_html": "<H3>testing</H3>",
            "media": {
                "snapshot_url": "http://mycamera.thing",
            },
            "delivery": {"default": {"data": {"footer": ""}}},
        },
    )
    await notification.initialize()
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = Path("/local/picture.jpg")
    await uut.deliver(
        Envelope(Delivery("default", context.delivery_config("default"), uut), notification, target=notification._target)
    )
    context.hass.services.async_call.assert_called_with(  # type:ignore
        "notify",
        "smtp",
        service_data={
            "target": ["tester9@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"images": ["/local/picture.jpg"], "html": '<H3>testing</H3><div><p><img src="cid:picture.jpg"></p></div>'},
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_discover_smtp_integration(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)

    with patch("homeassistant.components.smtp.notify.MailNotificationService.connection_is_valid"):
        assert await async_setup_component(
            hass,
            "notify",
            {
                "notify": [
                    {
                        "name": "mailservice",
                        "platform": "smtp",
                        "server": "localhost",
                        "encryption": "none",
                        "sender": "hass@localhost.org",
                        "recipient": ["tester@localhost.org"],
                    }
                ]
            },
        )
        await hass.async_block_till_done()

    await ctx.test_initialize()
    assert "DEFAULT_email" in ctx.delivery_registry.deliveries
    assert ctx.delivery_registry.deliveries["DEFAULT_email"].action == "notify.mailservice"


async def test_discover_no_smtp_integration(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    assert "DEFAULT_email" not in ctx.delivery_registry.deliveries


def test_pack_preheader() -> None:
    uut = EmailTransport(Mock(custom_template_path=None), {})

    assert (
        uut.pack_preheader("foo", {OPTION_PREHEADER_BLANK: "&nbsp;", OPTION_PREHEADER_LENGTH: 12})
        == "foo&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
    )
    assert uut.pack_preheader("foo", {}) == "foo"


async def test_deliver_with_data_key() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"plain_email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    await uut.deliver(
        Envelope(
            Delivery("plain_email", context.delivery_config("plain_email"), uut),
            Notification(context, message="hello there", title="testing"),
            target=Target(["tester1@assert.com"]),
            data={"data": {"custom_key": "custom_val"}},
        )
    )
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "smtp",
        service_data={
            "target": ["tester1@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"custom_key": "custom_val"},
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_with_preformatted_html_snapshot_url_and_image() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"default": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
    )

    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    notification = Notification(
        context,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={
            "message_html": "<H3>testing</H3>",
            "media": {"snapshot_url": "http://mycamera.thing"},
            "delivery": {"default": {"data": {"footer": ""}}},
        },
    )
    await notification.initialize()
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = Path("/local/picture.jpg")
    await uut.deliver(
        Envelope(
            Delivery("default", context.delivery_config("default"), uut),
            notification,
            target=Target(["tester9@assert.com"]),
            data={"media": {"snapshot_url": "http://mycamera.thing"}, "message_html": "<H3>testing</H3>"},
        )
    )
    call_args = context.hass.services.async_call.call_args  # type: ignore
    assert call_args is not None
    html = call_args.kwargs["service_data"]["data"]["html"]
    assert "mycamera.thing" in html


def test_email_extra_attributes_and_features() -> None:
    uut = EmailTransport(Mock(custom_template_path=None), {})
    attrs = uut.extra_attributes()
    assert "cached_templates" in attrs
    assert "custom_templates" in attrs
    assert "custom_email_templates" in attrs

    from custom_components.supernotify.model import TransportFeature

    features = uut.supported_features
    assert features & TransportFeature.MESSAGE


def test_email_custom_template_path_exception() -> None:
    class BadPath:
        def exists(self):
            raise OSError("bad path")

    ctx = Mock()
    ctx.custom_template_path = BadPath()
    uut = EmailTransport(ctx, {})
    assert uut.custom_email_template_path is None


async def test_email_auto_configure_no_smtp(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    result = uut.auto_configure(ctx.hass_api)
    assert result is None


async def test_deliver_with_template_and_image_path(hass: HomeAssistant, tmp_path: Path) -> None:
    template_dir = tmp_path / "email"
    template_dir.mkdir(parents=True)
    (template_dir / "test_with_image.html.j2").write_text("{{ alert.img.url if alert.img else 'no img' }}")
    ctx = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "test_with_image.html.j2",
            }
        },
        template_path=tmp_path,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    notification = Notification(
        ctx,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={"media": {"snapshot_url": "http://mycamera.thing"}},
    )
    await notification.initialize()
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = Path("/local/picture.jpg")
    await uut.deliver(
        Envelope(
            Delivery("test_email", ctx.delivery_config("test_email"), uut),
            notification,
            target=Target(["tester9@assert.com"]),
            data={"media": {"snapshot_url": "http://mycamera.thing"}},
        )
    )
    await ctx.hass.async_block_till_done()
    assert len(ctx.services["notify.smtp"].calls) == 1
    call_data = ctx.services["notify.smtp"].calls[0].data
    assert "data" in call_data
    assert call_data["data"]["html"]


async def test_render_template_empty_result(hass: HomeAssistant, tmp_path: Path) -> None:
    template_dir = tmp_path / "email"
    template_dir.mkdir(parents=True)
    (template_dir / "empty.html.j2").write_text("")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "empty.html.j2",
            }
        },
        template_path=tmp_path,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    result = await uut.render_template(
        "empty.html.j2",
        Envelope(Delivery("test_email", ctx.delivery_config("test_email"), uut), Notification(ctx, message="test")),
        {},
    )
    assert result is None


async def test_render_template_with_image_no_snapshot(hass: HomeAssistant, tmp_path: Path) -> None:
    from anyio import Path as AnyioPath

    template_dir = tmp_path / "email"
    template_dir.mkdir(parents=True)
    (template_dir / "img_tpl.html.j2").write_text("{{ alert.img.url if alert.img else 'no img' }}")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "img_tpl.html.j2",
            }
        },
        template_path=tmp_path,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    img_path = AnyioPath(tmp_path / "test_image.jpg")
    result = await uut.render_template(
        "img_tpl.html.j2",
        Envelope(Delivery("test_email", ctx.delivery_config("test_email"), uut), Notification(ctx, message="test")),
        {},
        image_path=img_path,
    )
    assert result is not None
    assert "cid:" in result


async def test_render_template_exception(hass: HomeAssistant, tmp_path: Path) -> None:
    from unittest.mock import patch

    template_dir = tmp_path / "email"
    template_dir.mkdir(parents=True)
    (template_dir / "bad.html.j2").write_text("{{ some_template }}")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "bad.html.j2",
            }
        },
        template_path=tmp_path,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    with patch.object(uut.context.hass_api, "template", side_effect=Exception("template error")):
        result = await uut.render_template(
            "bad.html.j2",
            Envelope(Delivery("test_email", ctx.delivery_config("test_email"), uut), Notification(ctx, message="test")),
            {},
        )
    assert result is None


async def test_render_template_not_found(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "nonexistent_template.html.j2",
            }
        },
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    result = await uut.render_template(
        "nonexistent_template.html.j2",
        Envelope(Delivery("test_email", ctx.delivery_config("test_email"), uut), Notification(ctx, message="test")),
        {},
    )
    assert result is None


async def test_template_cache_hit(tmp_path: Path) -> None:
    uut = EmailTransport(Mock(custom_template_path=None), {})
    first = await uut.load_template("default.html.j2")
    assert first is not None
    second = await uut.load_template("default.html.j2")
    assert second == first


async def test_find_default_template(tmp_path: Path) -> None:

    uut = EmailTransport(Mock(custom_template_path=tmp_path), {})
    html = await uut.load_template("default.html.j2")
    assert html.startswith("<!doctype html>")  # type:ignore

    async with await anyio.Path(tmp_path / "default.html.j2").open("w") as f:
        await f.write("{{ 1+1 }}")
    uut = EmailTransport(Mock(custom_template_path=tmp_path), {})
    assert await uut.load_template("default.html.j2") == "{{ 1+1 }}"

    (tmp_path / "email").mkdir()
    async with await anyio.Path(tmp_path / "email" / "default.html.j2").open("w") as f:
        await f.write("{{ 2+2 }}")
    uut = EmailTransport(Mock(custom_template_path=tmp_path), {})
    assert await uut.load_template("default.html.j2") == "{{ 2+2 }}"
