from pathlib import Path
from unittest.mock import Mock, patch

import anyio
from homeassistant.const import CONF_ACTION, CONF_EMAIL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from custom_components.supernotify import (
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

from .hass_setup_lib import TestingContext


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
