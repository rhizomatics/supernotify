from __future__ import annotations

import importlib.util
from contextlib import ExitStack
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

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
from homeassistant.setup import async_setup_component

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
    EMAIL_OPTION_MODE_DIRECT,
    EMAIL_OPTION_MODE_HA_SMTP,
    OPTION_MODE,
    OPTION_SENDER,
    OPTION_SENDER_NAME,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import SuppressionReason, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.email import OPTION_PREHEADER_BLANK, OPTION_PREHEADER_LENGTH, EmailTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

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
    return EmailTransport(
        Mock(custom_template_path=None), transport_config if transport_config is not None else SMTP_TRANSPORT_CONFIG
    )


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
    assert len(ctx.services["notify"]["smtp"].calls) == 1
    service_call: ServiceCall = ctx.services["notify"]["smtp"].calls[0]
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


def _smtp_uses_config_entry() -> bool:
    """Whether the installed HA version sets up smtp notify via a config entry import
    flow (and so a direct SMTP connection can be reused from it), rather than as a
    legacy discovered notify platform with no config entry to reuse."""
    return importlib.util.find_spec("homeassistant.components.smtp.config_flow") is not None


async def _setup_ha_smtp_notify(hass: HomeAssistant, extra_config: dict | None = None) -> None:
    config = {
        **(extra_config or {}),
        "notify": [
            {
                "name": "mailservice",
                "platform": "smtp",
                "server": "localhost",
                "encryption": "none",
                "sender": "hass@localhost.org",
                "recipient": ["tester@localhost.org"],
            },
        ],
    }
    if extra_config:
        assert await async_setup_component(hass, next(iter(extra_config)), config)

    with ExitStack() as stack:
        if _smtp_uses_config_entry():
            # HA >= 2026.x: smtp notify is set up via a config entry import flow
            stack.enter_context(patch("homeassistant.components.smtp.config_flow.validate_input", return_value={}))
            stack.enter_context(patch("homeassistant.components.smtp.helpers.SmtpClient.connect"))
        else:
            # older HA: smtp notify is a legacy discovered notify platform
            stack.enter_context(patch("homeassistant.components.smtp.notify.MailNotificationService.connection_is_valid"))
        assert await async_setup_component(hass, "notify", config)
        await hass.async_block_till_done()
    await hass.async_block_till_done()


async def test_discover_smtp_integration(hass: HomeAssistant) -> None:
    """With the HA smtp integration present and no explicit OPTION_MODE, the
    auto-configured delivery prefers direct sending (reusing the integration's own
    connection details) over the native notify.smtp action - the legacy notify-platform
    action path only wins if a delivery explicitly asks for EMAIL_OPTION_MODE_HA_SMTP."""
    ctx = TestingContext(homeassistant=hass)
    await _setup_ha_smtp_notify(hass, {"notify_events": {"token": "ABC"}})

    await ctx.test_initialize()
    assert "email" in ctx.delivery_registry.deliveries
    delivery = ctx.delivery_registry.deliveries["email"]
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    if _smtp_uses_config_entry():
        # a config entry exists to reuse a direct SMTP connection from
        assert delivery.options.get(OPTION_MODE) == EMAIL_OPTION_MODE_DIRECT
        assert uut.host == "localhost"
        assert uut.sender == "hass@localhost.org"
    else:
        # legacy discovered notify platform, no config entry to reuse a connection from
        assert delivery.options.get(OPTION_MODE) is None
        assert uut.host is None


async def test_discover_smtp_integration_explicit_ha_smtp_mode(hass: HomeAssistant) -> None:
    """A delivery that explicitly asks for EMAIL_OPTION_MODE_HA_SMTP still gets the
    discovered native notify.smtp action, even though a direct connection is also
    available (reused from the HA smtp integration)."""
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_OPTIONS: {OPTION_MODE: EMAIL_OPTION_MODE_HA_SMTP}},
        },
    )
    await _setup_ha_smtp_notify(hass)

    await ctx.test_initialize()
    assert ctx.delivery_registry.deliveries["email"].action == "notify.mailservice"


async def test_explicit_delivery_named_like_transport_absorbs_discovery(hass: HomeAssistant) -> None:
    """An explicit delivery literally named after its transport doesn't need its own
    connection details - it's merged with (and overrides) the auto-configured/discovered
    defaults, rather than being skipped in favour of a separate DEFAULT_email delivery."""
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_TEMPLATE: "minimal_test.html.j2"}},
    )
    await _setup_ha_smtp_notify(hass)

    await ctx.test_initialize()
    # merged into the explicit "email" delivery - no separate DEFAULT_email is created
    assert "DEFAULT_email" not in ctx.delivery_registry.deliveries
    assert "email" in ctx.delivery_registry.deliveries
    merged = ctx.delivery_registry.deliveries["email"]
    if _smtp_uses_config_entry():
        # discovered direct-mode connection fills the gap the explicit config left open
        assert merged.options.get(OPTION_MODE) == EMAIL_OPTION_MODE_DIRECT
    else:
        # legacy discovered notify platform, no config entry to reuse a connection from
        assert merged.options.get(OPTION_MODE) is None
    # explicit config is still honoured, regardless of whether the transport itself had
    # a usable connection/action at the time this delivery was first validated
    assert merged.template == "minimal_test.html.j2"


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


async def test_email_auto_configure_direct_connection_no_ha_smtp(hass: HomeAssistant) -> None:
    """No HA smtp notify service is registered, but a direct SMTP connection is
    configured on the transport - auto_configure() should still produce a usable
    delivery, sending direct rather than via a (non-existent) HA notify action."""
    ctx = TestingContext(homeassistant=hass, transports={TRANSPORT_EMAIL: SMTP_TRANSPORT_CONFIG})
    await ctx.test_initialize()
    uut = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    result = uut.auto_configure(ctx.hass_api)
    assert result is not None
    assert result.options.get(OPTION_MODE) == EMAIL_OPTION_MODE_DIRECT
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
    uut = EmailTransport(context, {})
    assert uut.validate_action(None) is False


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
    assert msg["From"] == "Home Assistant <hass@example.com>"


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
    uut = context.transport(TRANSPORT_EMAIL)

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
