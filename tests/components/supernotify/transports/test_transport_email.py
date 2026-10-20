from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest
from anyio import Path
from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import (
    CONF_ACTION,
    CONF_EMAIL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENDER,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from custom_components.supernotify.const import (
    ATTR_DATA,
    ATTR_DELIVERY,
    ATTR_MEDIA_SNAPSHOT_PATH,
    ATTR_TITLE,
    CONF_CONNECTION,
    CONF_DELIVERY_DEFAULTS,
    CONF_ENCRYPTION,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_TEMPLATE,
    CONF_TRANSPORT,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import SuppressionReason, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import TRANSPORT_SCHEMA
from custom_components.supernotify.transports.email import (
    EMAIL_OPTION_MODE_DIRECT,
    EMAIL_OPTION_MODE_HA_SMTP,
    OPTION_DEFAULT_TITLE,
    OPTION_MODE,
    OPTION_PREHEADER_BLANK,
    OPTION_PREHEADER_LENGTH,
    OPTION_SENDER,
    OPTION_SENDER_NAME,
    EmailTransport,
)
from tests.components.supernotify.hass_setup_lib import TestingContext, english_translations, set_state
from tests.components.supernotify.transports.schema_usage import SchemaCase, assert_schema_usage, sizes
from tests.components.supernotify.transports.transport_actions import setup_smtp, smtp_config_flow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

SMTP_CONNECTION = {
    CONF_HOST: "smtp.example.com",
}
SMTP_TRANSPORT_CONFIG = {
    CONF_CONNECTION: SMTP_CONNECTION,
    CONF_DELIVERY_DEFAULTS: {
        CONF_OPTIONS: {
            OPTION_SENDER: "hass@example.com",
        }
    },
}


def _direct_smtp_uut(transport_config: dict | None = None) -> EmailTransport:
    context = Mock(custom_template_path=None)
    context.hass_api.translations = english_translations
    context.hass_api.hass_name = "Our Home"
    context.hass_api.has_service.return_value = False
    return EmailTransport(context, transport_config if transport_config is not None else SMTP_TRANSPORT_CONFIG)


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
    set_state(ctx.hass_api, "device_tracker.joey_mctest", "home")
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
    assert len(ctx.services["notify"]["smtp"].calls) == 1
    service_call: ServiceCall = ctx.services["notify"]["smtp"].calls[0]
    assert service_call.data == {
        "target": ["tester9@assert.com"],
        "title": "testing",
        "message": "hello there",
        "data": {"html": "<H1>testing</H1>\n<H2>Joey is home</H2>"},
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
            # the notification's snapshot_url, so the image links to it
            "data": {
                "images": ["/local/picture.jpg"],
                "html": '<H3>testing</H3><div><p><a href="http://mycamera.thing"><img src="cid:picture.jpg"/></a></p></div>',
            },
        },
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_discover_smtp_integration(hass: HomeAssistant) -> None:
    """With the HA smtp integration present and no explicit OPTION_MODE, the auto-configured
    delivery defaults to direct sending either way - OPTION_MODE: direct is always the
    transport-wide default now (see EmailTransport.default_config()), regardless of whether a
    config entry exists to reuse a real connection from. Whether direct sending is actually
    usable at runtime is EmailTransport.local_smtp's job (see _send()), not this option -
    the legacy notify-platform action path only wins if a delivery explicitly asks for
    EMAIL_OPTION_MODE_HA_SMTP."""
    ctx = TestingContext(homeassistant=hass)
    await setup_smtp(hass, {"notify_events": {"token": "ABC"}})

    await ctx.test_initialize()
    assert "email" in ctx.delivery_registry.deliveries
    delivery = ctx.delivery_registry.deliveries["email"]
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    assert delivery.options.get(OPTION_MODE) == EMAIL_OPTION_MODE_DIRECT
    if smtp_config_flow():
        # a config entry exists to reuse a direct SMTP connection from
        assert uut.host == "localhost"
        assert uut.sender == "hass@localhost.org"
        assert uut.local_smtp is True
    else:
        # legacy discovered notify platform, no config entry to reuse a connection from
        assert uut.host is None
        assert uut.local_smtp is False


async def test_discover_smtp_integration_explicit_ha_smtp_mode(hass: HomeAssistant) -> None:
    """A delivery that explicitly asks for EMAIL_OPTION_MODE_HA_SMTP still gets the
    discovered native notify.smtp action, even though a direct connection is also
    available (reused from the HA smtp integration)."""
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.gmail",
                CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_HA_SMTP},
            },
        },
    )
    await setup_smtp(hass)

    await ctx.test_initialize()
    assert ctx.delivery_registry.deliveries["email"].action == "notify.gmail"


async def test_explicit_delivery_named_like_transport_overrides_discovery(hass: HomeAssistant) -> None:
    """An explicit delivery literally named after its transport doesn't need its own
    connection details - it's overrides the auto-configured/discovered delivery"""

    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_TEMPLATE: "minimal_test.html.j2"}},
    )
    await setup_smtp(hass)

    await ctx.test_initialize()
    assert "email" in ctx.delivery_registry.deliveries
    delivery = ctx.delivery_registry.deliveries["email"]
    assert delivery.template == "minimal_test.html.j2"


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
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL, force=True))
    result = uut.build_standard_deliveries(ctx.hass_api)
    assert result == {}


async def test_email_auto_configure_direct_connection_no_ha_smtp(hass: HomeAssistant) -> None:
    """No HA smtp notify service is registered, but a direct SMTP connection is
    configured on the transport - build_standard_deliveries() should still produce a
    usable delivery, sending direct rather than via a (non-existent) HA notify action."""
    ctx = TestingContext(homeassistant=hass, transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG})
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_EMAIL in result
    assert "email" in ctx.delivery_registry.deliveries
    assert ctx.delivery_registry.deliveries["email"].options.get(OPTION_MODE) == EMAIL_OPTION_MODE_DIRECT


async def test_deliver_with_template_and_image_path(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    template_dir: Path = tmp_aiopath / "email"
    await template_dir.mkdir(parents=True)
    await (template_dir / "test_with_image.html.j2").write_text("{{ alert.img.url if alert.img else 'no img' }}")
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
        template_path=tmp_aiopath,
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
    assert len(ctx.services["notify"]["smtp"].calls) == 1
    call_data = ctx.services["notify"]["smtp"].calls[0].data
    assert "data" in call_data
    assert call_data["data"]["html"]


async def test_render_template_empty_result(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    template_dir = tmp_aiopath / "email"
    await template_dir.mkdir(parents=True)
    await (template_dir / "empty.html.j2").write_text("")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "empty.html.j2",
            }
        },
        template_path=tmp_aiopath,
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


async def test_render_template_with_image_no_snapshot(hass: HomeAssistant, tmp_aiopath: Path) -> None:

    template_dir = tmp_aiopath / "email"
    await template_dir.mkdir(parents=True)
    await (template_dir / "img_tpl.html.j2").write_text("{{ alert.img.url if alert.img else 'no img' }}")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "img_tpl.html.j2",
            }
        },
        template_path=tmp_aiopath,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))

    img_path = tmp_aiopath / "test_image.jpg"
    result = await uut.render_template(
        "img_tpl.html.j2",
        Envelope(Delivery("test_email", ctx.delivery_config("test_email"), uut), Notification(ctx, message="test")),
        {},
        image_path=img_path,
    )
    assert result is not None
    assert "cid:" in result


async def test_render_template_exception(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    from unittest.mock import patch

    template_dir = tmp_aiopath / "email"
    await template_dir.mkdir(parents=True)
    await (template_dir / "bad.html.j2").write_text("{{ some_template }}")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "bad.html.j2",
            }
        },
        template_path=tmp_aiopath,
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


async def test_template_cache_hit(tmp_aiopath: Path) -> None:
    uut = EmailTransport(Mock(custom_template_path=None), {})
    first = await uut.load_template("default.html.j2")
    assert first is not None
    second = await uut.load_template("default.html.j2")
    assert second == first


async def test_find_default_template(tmp_aiopath: Path) -> None:
    ctx = Mock(custom_template_path=tmp_aiopath)
    uut = EmailTransport(ctx, {})
    await uut.initialize()
    html = await uut.load_template("default.html.j2")
    assert html.startswith("<!doctype html>")  # type:ignore

    async with await (tmp_aiopath / "default.html.j2").open("w") as f:
        await f.write("{{ 1+1 }}")
    ctx = Mock(custom_template_path=tmp_aiopath)
    uut = EmailTransport(ctx, {})
    await uut.initialize()
    assert await uut.load_template("default.html.j2") == "{{ 1+1 }}"

    await (tmp_aiopath / "email").mkdir()
    async with await (tmp_aiopath / "email" / "default.html.j2").open("w") as f:
        await f.write("{{ 2+2 }}")
    ctx = Mock(custom_template_path=tmp_aiopath)
    uut = EmailTransport(ctx, {})
    await uut.initialize()
    assert await uut.load_template("default.html.j2") == "{{ 2+2 }}"


# Direct SMTP connection handling


def test_direct_smtp_validate_action_without_connection() -> None:
    context = Mock(custom_template_path=None)
    context.hass_api.find_config_entry_data.return_value = None
    context.hass_api.find_service.return_value = None
    context.hass_api.has_service.return_value = False
    uut = EmailTransport(context, {})
    assert uut.validate_action(None) is False


def test_validate_action_with_smtp_send_message() -> None:
    context = Mock(custom_template_path=None)
    context.hass_api.find_config_entry_data.return_value = None
    context.hass_api.find_service.return_value = None
    context.hass_api.has_service.side_effect = lambda domain, service: (domain, service) == ("smtp", "send_message")
    uut = EmailTransport(context, {})
    assert uut.validate_action(None) is True


def test_direct_smtp_validate_action_with_connection() -> None:
    uut = _direct_smtp_uut()
    assert uut.validate_action(None) is True


def test_reuses_ha_smtp_connection_when_not_configured() -> None:
    context = Mock(custom_template_path=None)
    context.hass_api.find_config_entry_data.return_value = {
        "server": "ha-smtp.example.com",
        CONF_PORT: 465,
        CONF_ENCRYPTION: "tls",
        CONF_USERNAME: "ha_user",
        CONF_PASSWORD: "ha_pass",
        CONF_VERIFY_SSL: False,
        CONF_SENDER: "ha@example.com",
        OPTION_SENDER_NAME: "HA Notifier",
    }
    uut = EmailTransport(context, {})

    context.hass_api.find_config_entry_data.assert_called_once_with("smtp")
    assert uut.host == "ha-smtp.example.com"
    assert uut.port == 465
    assert uut.encryption == "tls"
    assert uut.username == "ha_user"
    assert uut.password == "ha_pass"
    assert uut.verify_ssl is False
    assert uut.sender == "ha@example.com"
    assert uut.sender_name == "HA Notifier"
    assert uut.validate_action(None) is True


def test_existing_connection_not_overridden_by_ha_smtp() -> None:
    context = Mock(custom_template_path=None)
    uut = EmailTransport(context, SMTP_TRANSPORT_CONFIG)
    assert uut.host == "smtp.example.com"
    context.hass_api.find_config_entry_data.assert_not_called()


async def test_build_message_plain() -> None:
    uut = _direct_smtp_uut({
        **SMTP_TRANSPORT_CONFIG,
        CONF_DELIVERY_DEFAULTS: {
            CONF_OPTIONS: {
                OPTION_SENDER_NAME: "Home Assistant",
            }
        },
    })
    msg = await uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], None, "001")
    assert isinstance(msg, MIMEText)
    assert msg["Subject"] == "testing"
    assert msg["To"] == "tester1@assert.com"
    assert msg["From"] == "Home Assistant <>"
    assert msg["Importance"] is None
    assert msg["Priority"] is None
    assert msg["X-Priority"] is None
    assert msg["X-MSMail-Priority"] is None


async def test_build_message_default_title() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message({ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], None, "003")
    assert msg["Subject"] == "Home Assistant Notification"


async def test_build_message_explicit_title_overrides_default() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], None, "004")
    assert msg["Subject"] == "testing"


async def test_build_message_html() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_DATA: {"html": "<h1>hi</h1>"}},
        ["tester1@assert.com"],
        None,
        "002",
    )
    assert isinstance(msg, MIMEMultipart)
    # the home's name when there's no sender_name
    assert msg["From"] == "Our Home <hass@example.com>"


async def test_build_message_with_image_attachment(tmp_path: object) -> None:
    image_path = tmp_path / "picture.jpg"  # type: ignore[operator]  # ty: ignore[unsupported-operator]
    image_path.write_bytes(b"\xff\xd8\xff\xe0notreallyajpegbutclosenough")

    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_DATA: {"images": [str(image_path)]}},
        ["tester1@assert.com"],
        None,
        "003",
    )
    assert isinstance(msg, MIMEMultipart)
    attachments = [part for part in msg.walk() if part.get("Content-ID")]
    assert len(attachments) == 1
    assert attachments[0]["Content-ID"] == "<picture.jpg>"


async def test_build_message_importance_high() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_HIGH, "004"
    )
    assert msg["Importance"] == "high"
    assert msg["Priority"] == "urgent"
    assert msg["X-Priority"] == "2"
    assert msg["X-MSMail-Priority"] == "High"


async def test_build_message_importance_normal() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_MEDIUM, "005"
    )
    assert msg["Importance"] == "normal"
    assert msg["Priority"] == "normal"
    assert msg["X-Priority"] == "3"
    assert msg["X-MSMail-Priority"] == "Normal"


async def test_build_message_importance_low() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_LOW, "006"
    )
    assert msg["Importance"] == "low"
    assert msg["Priority"] == "non-urgent"
    assert msg["X-Priority"] == "4"
    assert msg["X-MSMail-Priority"] == "Low"


def test_send_smtp_starttls() -> None:
    uut = _direct_smtp_uut({
        **SMTP_TRANSPORT_CONFIG,
        CONF_CONNECTION: {**SMTP_CONNECTION, CONF_USERNAME: "bob", CONF_PASSWORD: "secret", CONF_ENCRYPTION: "starttls"},
    })
    with (
        patch("custom_components.supernotify.transports.email.smtplib.SMTP") as mock_smtp_cls,
        patch("custom_components.supernotify.transports.email.create_client_context"),
    ):
        mock_client = mock_smtp_cls.return_value
        uut._send_smtp(MIMEText("hi"), ["tester1@assert.com"])

        mock_smtp_cls.assert_called_with("smtp.example.com", 587, timeout=5)
        mock_client.starttls.assert_called_once()
        mock_client.login.assert_called_with("bob", "secret")
        sent_sender, sent_addresses, sent_body = mock_client.sendmail.call_args.args
        assert sent_sender == "hass@example.com"
        assert sent_addresses == ["tester1@assert.com"]
        assert sent_body.endswith("hi")
        mock_client.quit.assert_called_once()


def test_send_smtp_tls() -> None:
    uut = _direct_smtp_uut({
        **SMTP_TRANSPORT_CONFIG,
        CONF_CONNECTION: {**SMTP_CONNECTION, CONF_ENCRYPTION: "tls", CONF_PORT: 465},
    })
    with (
        patch("custom_components.supernotify.transports.email.smtplib.SMTP_SSL") as mock_smtp_ssl_cls,
        patch("custom_components.supernotify.transports.email.create_client_context"),
    ):
        mock_client = mock_smtp_ssl_cls.return_value
        uut._send_smtp(MIMEText("hi"), ["tester1@assert.com"])

        mock_smtp_ssl_cls.assert_called_once()
        mock_client.starttls.assert_not_called()
        mock_client.login.assert_not_called()
        sent_sender, sent_addresses, sent_body = mock_client.sendmail.call_args.args
        assert sent_sender == "hass@example.com"
        assert sent_addresses == ["tester1@assert.com"]
        assert sent_body.endswith("hi")


async def test_deliver_direct_smtp_skips_without_connection() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"direct_smtp": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_DIRECT}}},
        transports={TRANSPORT_EMAIL: {}},
    )
    await context.test_initialize()
    # the "direct_smtp" delivery fails validate_action() (no action, no host/sender), so
    # never registers - force a bare instance to unit-test deliver()'s own graceful skip
    uut = context.transport(TRANSPORT_EMAIL, force=True)

    envelope = Envelope(
        Delivery("direct_smtp", context.delivery_config("direct_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(EmailTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_ACTION
    mock_send.assert_not_called()


async def test_deliver_direct_smtp_skips_without_target() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"direct_smtp": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_DIRECT}}},
        transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    envelope = Envelope(
        Delivery("direct_smtp", context.delivery_config("direct_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(),
    )
    with patch.object(EmailTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_TARGET
    mock_send.assert_not_called()


async def test_deliver_direct_smtp(hass: HomeAssistant) -> None:
    context = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"direct_smtp": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_DIRECT}}},
        transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    envelope = Envelope(
        Delivery("direct_smtp", context.delivery_config("direct_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(EmailTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)

    assert result is True
    assert envelope.delivered == 1
    assert len(envelope.calls) == 1
    assert envelope.calls[0].target_data == {ATTR_TARGET: ["tester1@assert.com"]}
    mock_send.assert_called_once()
    sent_msg = mock_send.call_args.args[0]
    assert sent_msg["To"] == "tester1@assert.com"
    assert sent_msg["Subject"] == "testing"


async def test_deliver_ha_smtp_mode_uses_action_call() -> None:
    """Explicitly setting OPTION_MODE to EMAIL_OPTION_MODE_HA_SMTP uses the HA notify action,
    even when a direct SMTP connection is configured on the transport - it's not enough for a
    connection to just be available, the delivery has to opt into direct sending."""
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={
            "ha_smtp": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_HA_SMTP},
            }
        },
        transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)

    with patch.object(EmailTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(
            Envelope(
                Delivery("ha_smtp", context.delivery_config("ha_smtp"), uut),
                Notification(context, message="hello there", title="testing"),
                target=Target(["tester1@assert.com"]),
            )
        )

    assert result is True
    mock_send.assert_not_called()
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "smtp",
        service_data={"target": ["tester1@assert.com"], "title": "testing", "message": "hello there"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_ha_smtp_mode_uses_default_action() -> None:
    """OPTION_MODE=EMAIL_OPTION_MODE_HA_SMTP with no explicit delivery `action:` falls back
    to the transport's own discovered default action (self.ha_action) - distinct from
    test_deliver_ha_smtp_mode_uses_action_call, which sets an explicit per-delivery action."""
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={
            "ha_smtp": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_HA_SMTP},
            }
        },
        services={"notify": [{"action": "mailservice", "module": "homeassistant.components.smtp.notify"}]},
    )
    # a truthy smtp config entry is needed to get past the early return in
    # EmailTransport._reuse_ha_smtp_connection() before it discovers self.ha_action - the
    # default mock hass returns an empty (falsy) data dict for every domain
    context.hass.config_entries.async_entries = lambda domain, **_kwargs: (  # type: ignore # ty: ignore[invalid-assignment]
        [Mock(data={CONF_SENDER: "hass@example.com"})] if domain == "smtp" else [Mock(data={})]
    )
    await context.test_initialize()
    uut = cast("EmailTransport", context.transport(TRANSPORT_EMAIL))
    assert uut.ha_action == "notify.mailservice"

    result = await uut.deliver(
        Envelope(
            Delivery("ha_smtp", context.delivery_config("ha_smtp"), uut),
            Notification(context, message="hello there", title="testing"),
            target=Target(["tester1@assert.com"]),
        )
    )

    assert result is True
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "notify",
        "mailservice",
        service_data={"target": ["tester1@assert.com"], "title": "testing", "message": "hello there"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


def test_transport_schema_sender_stays_a_string() -> None:
    """Regression test: vol.Email (uncalled) previously returned a validator function.

    instead of the validated address, so downstream code (e.g. email.utils.formataddr)
    blew up trying to call str methods on a function object.
    """
    validated = TRANSPORT_SCHEMA({
        CONF_CONNECTION: {CONF_HOST: "smtp.example.com"},
        CONF_DELIVERY_DEFAULTS: {CONF_OPTIONS: {OPTION_SENDER: "hass@example.com"}},
    })
    assert isinstance(validated[CONF_DELIVERY_DEFAULTS][CONF_OPTIONS][OPTION_SENDER], str)
    assert validated[CONF_DELIVERY_DEFAULTS][CONF_OPTIONS][OPTION_SENDER] == "hass@example.com"


@sizes
async def test_schema_usage(hass: HomeAssistant, maximal: bool) -> None:
    case = SchemaCase(
        EmailTransport,
        ["tester@example.org"],
        {"notify.smtp"},
        delivery={"action": "notify.smtp"},
        maximal_data={"footer": "Sent by {e.delivery_name}", "data": {"sender_name": "Home"}},
    )
    await assert_schema_usage(hass, case, maximal)


async def _sent_by_notify_smtp(delivery: dict, action_data: dict | None = None, **kwargs: object) -> dict:
    context = TestingContext(
        deliveries={"mail": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", **delivery}}, **kwargs
    )
    await context.test_initialize()
    notification = Notification(
        context, message="hello there", target=["a@b.com"], action_data={"delivery": ["mail"], **(action_data or {})}
    )
    await notification.initialize()
    await notification.deliver()
    return context.hass.services.async_call.call_args.kwargs["service_data"]  # type: ignore


async def test_smtp_keys_in_data_are_passed_on() -> None:
    """Regression: smtp's own `html` and `images` were only passed on from a nested `data`"""
    sent = await _sent_by_notify_smtp({"data": {"html": "<b>hi</b>", "images": ["/tmp/a.jpg"]}}, {"data": {"cc": "c@d.com"}})

    assert sent["data"] == {"html": "<b>hi</b>", "images": ["/tmp/a.jpg"], "cc": "c@d.com"}


async def test_nested_data_is_moved_up(caplog: pytest.LogCaptureFixture) -> None:
    sent = await _sent_by_notify_smtp({"data": {"data": {"html": "<b>old</b>", "cc": "old@d.com"}, "cc": "new@d.com"}})

    assert sent["data"] == {"html": "<b>old</b>", "cc": "new@d.com"}
    assert "rather than in a nested `data`" in caplog.text


async def test_html_given_wins_over_message_html() -> None:
    sent = await _sent_by_notify_smtp({"data": {"html": "<b>own</b>"}}, {"message_html": "<i>supernotify</i>"})

    assert sent["data"] == {"html": "<b>own</b>"}


async def test_supernotify_keys_are_not_passed_on() -> None:
    sent = await _sent_by_notify_smtp({"data": {"footer": "-- sent by {e.delivery_name}", "action_url": "http://x"}})

    assert sent["message"] == "hello there\n\n-- sent by mail"
    assert "data" not in sent


async def test_grabbed_image_is_added_to_given_images() -> None:
    context = TestingContext(deliveries={"mail": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}})
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)
    notification = Notification(context, message="hello there")
    await notification.initialize()
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = Path("/local/picture.jpg")
    await uut.deliver(
        Envelope(
            Delivery("mail", context.delivery_config("mail"), uut),
            notification,
            target=Target(["a@b.com"]),
            data={"images": ["/tmp/a.jpg"]},
        )
    )

    sent = context.hass.services.async_call.call_args.kwargs["service_data"]  # type: ignore
    assert sent["data"]["images"] == ["/tmp/a.jpg", "/local/picture.jpg"]


async def test_template_gets_notification_snapshot_url(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    """Regression: the notification's own media.snapshot_url was only looked for in `data`"""
    template_dir: Path = tmp_aiopath / "email"
    await template_dir.mkdir(parents=True)
    await (template_dir / "img.html.j2").write_text("{{ alert.img.url }}|{{ alert.img.desc }}")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"mail": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", CONF_TEMPLATE: "img.html.j2"}},
        template_path=tmp_aiopath,
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    notification = Notification(ctx, message="hello there", action_data={"media": {"snapshot_url": "http://mycamera.thing"}})
    await notification.initialize()
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = Path("/local/picture.jpg")
    await uut.deliver(Envelope(Delivery("mail", ctx.delivery_config("mail"), uut), notification, target=Target(["a@b.com"])))
    await ctx.hass.async_block_till_done()

    assert ctx.services["notify"]["smtp"].calls[0].data["data"]["html"] == "http://mycamera.thing|Snapshot Image"


async def test_template_lines_are_kept_as_written(tmp_aiopath: Path) -> None:
    await (tmp_aiopath / "lines.html.j2").write_text("<pre>\none\ntwo\n</pre>\n")
    uut = EmailTransport(Mock(custom_template_path=tmp_aiopath), {})
    await uut.initialize()

    assert await uut.load_template("lines.html.j2") == "<pre>\none\ntwo\n</pre>\n"


async def test_build_message_uses_delivery_sender_options() -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_MESSAGE: "hello there"},
        ["tester1@assert.com"],
        None,
        "005",
        {OPTION_SENDER: "alarm@example.com", OPTION_SENDER_NAME: "Alarm", OPTION_DEFAULT_TITLE: "Alarm!"},
    )

    assert msg["From"] == "Alarm <alarm@example.com>"
    assert msg["Subject"] == "Alarm!"


async def test_deliver_direct_smtp_uses_delivery_sender(hass: HomeAssistant) -> None:
    context = TestingContext(
        homeassistant=hass,
        deliveries={
            "direct_smtp": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_DIRECT, OPTION_SENDER: "alarm@example.com"},
            }
        },
        transports={TRANSPORT_EMAIL: {CONF_CONNECTION: SMTP_CONNECTION}},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)
    envelope = Envelope(
        Delivery("direct_smtp", context.delivery_config("direct_smtp"), uut),
        Notification(context, message="hello there"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(EmailTransport, "_send_smtp") as mock_send:
        assert await uut.deliver(envelope) is True

    assert mock_send.call_args.args[2] == "alarm@example.com"
    assert mock_send.call_args.args[0]["From"] == f"{hass.config.location_name} <alarm@example.com>"


async def test_no_default_delivery_without_sender(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """As for Home Assistant's own SMTP, a connection without a sender doesn't send"""
    ctx = TestingContext(homeassistant=hass, transports={TRANSPORT_EMAIL: {CONF_CONNECTION: SMTP_CONNECTION}})
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL, force=True))
    await uut.initialize()

    assert uut.build_standard_deliveries(ctx.hass_api) == {}
    assert "has no sender" in caplog.text


async def test_deliver_direct_smtp_failure_is_recorded(hass: HomeAssistant) -> None:
    context = TestingContext(
        homeassistant=hass,
        deliveries={"direct_smtp": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_DIRECT}}},
        transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_EMAIL)
    envelope = Envelope(
        Delivery("direct_smtp", context.delivery_config("direct_smtp"), uut),
        Notification(context, message="hello there"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(EmailTransport, "_send_smtp", side_effect=smtplib.SMTPAuthenticationError(535, b"bad password")):
        assert await uut.deliver(envelope) is False

    assert envelope.delivered == 0
    assert envelope.error_count == 1
    assert envelope.failed_calls[0].target_data == {ATTR_TARGET: ["tester1@assert.com"]}
    assert "bad password" in (envelope.failed_calls[0].exception or "")


async def test_missing_attachment_is_left_out(tmp_path: object) -> None:
    uut = _direct_smtp_uut()
    msg = await uut._build_message(
        {ATTR_MESSAGE: "hello there", ATTR_DATA: {"images": [str(tmp_path / "gone.jpg")]}},  # type: ignore[operator]  # ty: ignore[unsupported-operator]
        ["tester1@assert.com"],
        None,
        "006",
    )

    assert isinstance(msg, MIMEMultipart)
    assert len(msg.get_payload()) == 1  # type: ignore[arg-type]  # only the text, no attachment


async def _sent_by_smtp_send_message(
    hass: HomeAssistant, targets: list[str], action_data: dict | None = None, legacy_action: bool = False
) -> tuple[list[ServiceCall], Envelope]:
    # smtp.send_message only exists in newer HA versions
    services = pytest.importorskip("homeassistant.components.smtp.services")
    SERVICE_SEND_MESSAGE_SCHEMA = services.SERVICE_SEND_MESSAGE_SCHEMA
    from pytest_homeassistant_custom_component.common import async_mock_service

    calls: list[ServiceCall] = async_mock_service(hass, "smtp", "send_message", schema=SERVICE_SEND_MESSAGE_SCHEMA)
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"mail": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_HA_SMTP}}},
        services={"notify": ["smtp"]} if legacy_action else None,
    )
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    if legacy_action:
        uut.ha_action = "notify.smtp"
    notification = Notification(ctx, message="hello there", title="testing", action_data=action_data)
    await notification.initialize()
    envelope = Envelope(Delivery("mail", ctx.delivery_config("mail"), uut), notification, target=Target(targets))
    with patch.object(ctx.hass_api, "smtp_recipients", return_value={"alice@example.com": "notify.alice"}):
        await uut.deliver(envelope)
    await hass.async_block_till_done()
    return calls, envelope


async def test_ha_smtp_mode_uses_smtp_send_message(hass: HomeAssistant) -> None:
    calls, envelope = await _sent_by_smtp_send_message(
        hass,
        ["alice@example.com"],
        {"priority": "critical", "message_html": "<b>hello</b>", "data": {"cc": "not@for.smtp"}},
    )

    assert envelope.delivered == 1
    assert len(calls) == 1
    assert dict(calls[0].data) == {
        "entity_id": ["notify.alice"],
        "message": "hello there",
        "title": "testing",
        "html": "<b>hello</b>",
        "priority": "highest",  # cc isn't a field of smtp.send_message, so left out
    }


async def test_smtp_send_message_attaches_camera_when_snapshot_not_in_media_dirs(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        return_value=Path("/config/supernotify/media/image/snap.jpg"),
    ):
        calls, _ = await _sent_by_smtp_send_message(
            hass, ["alice@example.com"], {"media": {"camera_entity_id": "camera.porch"}}
        )

    assert calls[0].data["attachments"] == [
        {
            "media_source": {"media_content_id": "media-source://camera/camera.porch", "media_content_type": "image/jpeg"},
            "filename": "snap.jpg",
            "content_id": "snap.jpg",
        }
    ]


async def test_smtp_send_message_attaches_snapshot_from_media_dirs(hass: HomeAssistant) -> None:
    hass.config.media_dirs = {"supernotify": "/config/media/supernotify"}
    with patch(
        "custom_components.supernotify.envelope.Envelope.grab_image",
        return_value=Path("/config/media/supernotify/image/snap.jpg"),
    ):
        calls, _ = await _sent_by_smtp_send_message(hass, ["alice@example.com"])

    assert calls[0].data["attachments"][0]["media_source"]["media_content_id"] == (
        "media-source://media_source/supernotify/image/snap.jpg"
    )


async def test_smtp_send_message_others_go_by_legacy_action(hass: HomeAssistant) -> None:
    calls, envelope = await _sent_by_smtp_send_message(hass, ["alice@example.com", "bob@example.com"], legacy_action=True)

    assert len(calls) == 1
    assert [c.action for c in envelope.calls] == ["send_message", "smtp"]
    assert envelope.calls[1].action_data[ATTR_TARGET] == ["bob@example.com"]  # type: ignore[index]


async def test_smtp_send_message_others_left_out_without_legacy_action(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    calls, _ = await _sent_by_smtp_send_message(hass, ["alice@example.com", "bob@example.com"])

    assert len(calls) == 1
    assert "Not emailing bob@example.com" in caplog.text


async def test_data_keys_select_prunes_passed_on_data() -> None:
    sent = await _sent_by_notify_smtp({
        "data": {"html": "<b>hi</b>", "cc": "c@d.com"},
        CONF_OPTIONS: {"data_keys_select": {"exclude": ["cc"]}},
    })

    assert sent["data"] == {"html": "<b>hi</b>"}
