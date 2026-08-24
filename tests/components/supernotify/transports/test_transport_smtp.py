from __future__ import annotations

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

from custom_components.supernotify.const import (
    CONF_CONNECTION,
    CONF_DELIVERY_DEFAULTS,
    CONF_ENCRYPTION,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_TRANSPORT,
    OPTION_SENDER,
    OPTION_SENDER_NAME,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    TRANSPORT_SMTP,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import SuppressionReason, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.smtp import SmtpTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

CONNECTION = {
    CONF_HOST: "smtp.example.com",
}
TRANSPORT_CONFIG = {
    CONF_CONNECTION: CONNECTION,
    CONF_DELIVERY_DEFAULTS: {
        CONF_OPTIONS: {
            OPTION_SENDER: "hass@example.com",
        }
    },
}


def _uut(transport_config: dict | None = None) -> SmtpTransport:
    return SmtpTransport(
        Mock(custom_template_path=None), transport_config if transport_config is not None else TRANSPORT_CONFIG
    )


def test_auto_configure_without_connection() -> None:
    uut = SmtpTransport(Mock(custom_template_path=None), {})
    assert uut.auto_configure(Mock()) is None
    assert uut.validate_action(None) is False


def test_auto_configure_with_connection() -> None:
    uut = _uut()
    assert uut.auto_configure(Mock()) is uut.delivery_defaults
    assert uut.validate_action(None) is True


def test_build_message_plain() -> None:
    uut = _uut({
        **TRANSPORT_CONFIG,
        CONF_DELIVERY_DEFAULTS: {
            CONF_OPTIONS: {
                OPTION_SENDER_NAME: "Home Assistant",
            }
        },
    })
    msg = uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], None)
    assert isinstance(msg, MIMEText)
    assert msg["Subject"] == "testing"
    assert msg["To"] == "tester1@assert.com"
    assert msg["From"] == "Home Assistant <>"
    assert msg["Importance"] is None
    assert msg["Priority"] is None
    assert msg["X-Priority"] is None
    assert msg["X-MSMail-Priority"] is None


def test_build_message_html() -> None:
    uut = _uut()
    msg = uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_DATA: {"html": "<h1>hi</h1>"}},
        ["tester1@assert.com"],
        None,
    )
    assert isinstance(msg, MIMEMultipart)
    assert msg["From"] == "Home Assistant <hass@example.com>"


def test_build_message_with_image_attachment(tmp_path: object) -> None:
    image_path = tmp_path / "picture.jpg"  # type: ignore[operator]
    image_path.write_bytes(b"\xff\xd8\xff\xe0notreallyajpegbutclosenough")

    uut = _uut()
    msg = uut._build_message(
        {ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_DATA: {"images": [str(image_path)]}},
        ["tester1@assert.com"],
        None,
    )
    assert isinstance(msg, MIMEMultipart)
    attachments = [part for part in msg.walk() if part.get("Content-ID")]
    assert len(attachments) == 1
    assert attachments[0]["Content-ID"] == "<picture.jpg>"


def test_build_message_importance_high() -> None:
    uut = _uut()
    msg = uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_HIGH)
    assert msg["Importance"] == "High"
    assert msg["Priority"] == "urgent"
    assert msg["X-Priority"] == "2"
    assert msg["X-MSMail-Priority"] == "High"


def test_build_message_importance_normal() -> None:
    uut = _uut()
    msg = uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_MEDIUM)
    assert msg["Importance"] == "Normal"
    assert msg["Priority"] == "normal"
    assert msg["X-Priority"] == "3"
    assert msg["X-MSMail-Priority"] == "Normal"


def test_build_message_importance_low() -> None:
    uut = _uut()
    msg = uut._build_message({ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there"}, ["tester1@assert.com"], PRIORITY_LOW)
    assert msg["Importance"] == "Low"
    assert msg["Priority"] == "non-urgent"
    assert msg["X-Priority"] == "4"
    assert msg["X-MSMail-Priority"] == "Low"


def test_send_smtp_starttls() -> None:
    uut = _uut({
        **TRANSPORT_CONFIG,
        CONF_CONNECTION: {**CONNECTION, CONF_USERNAME: "bob", CONF_PASSWORD: "secret", CONF_ENCRYPTION: "starttls"},
    })
    with (
        patch("custom_components.supernotify.transports.smtp.smtplib.SMTP") as mock_smtp_cls,
        patch("custom_components.supernotify.transports.smtp.create_client_context"),
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
    uut = _uut({**TRANSPORT_CONFIG, CONF_CONNECTION: {**CONNECTION, CONF_ENCRYPTION: "tls", CONF_PORT: 465}})
    with (
        patch("custom_components.supernotify.transports.smtp.smtplib.SMTP_SSL") as mock_smtp_ssl_cls,
        patch("custom_components.supernotify.transports.smtp.create_client_context"),
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


async def test_deliver_skips_without_connection() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"plain_smtp": {CONF_TRANSPORT: TRANSPORT_SMTP}},
        transports={TRANSPORT_SMTP: {}},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_SMTP)

    envelope = Envelope(
        Delivery("plain_smtp", context.delivery_config("plain_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(SmtpTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_ACTION
    mock_send.assert_not_called()


async def test_deliver_skips_without_target() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"plain_smtp": {CONF_TRANSPORT: TRANSPORT_SMTP}},
        transports={TRANSPORT_SMTP: TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_SMTP)

    envelope = Envelope(
        Delivery("plain_smtp", context.delivery_config("plain_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(),
    )
    with patch.object(SmtpTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)
    assert result is False
    assert envelope.skipped == 1
    assert envelope.skip_reason == SuppressionReason.NO_TARGET
    mock_send.assert_not_called()


async def test_deliver(hass: HomeAssistant) -> None:
    context = TestingContext(
        homeassistant=hass,
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        deliveries={"plain_smtp": {CONF_TRANSPORT: TRANSPORT_SMTP}},
        transports={TRANSPORT_SMTP: TRANSPORT_CONFIG},
    )
    await context.test_initialize()
    uut = context.transport(TRANSPORT_SMTP)

    envelope = Envelope(
        Delivery("plain_smtp", context.delivery_config("plain_smtp"), uut),
        Notification(context, message="hello there", title="testing"),
        target=Target(["tester1@assert.com"]),
    )
    with patch.object(SmtpTransport, "_send_smtp") as mock_send:
        result = await uut.deliver(envelope)

    assert result is True
    assert envelope.delivered == 1
    assert len(envelope.calls) == 1
    assert envelope.calls[0].target_data == {ATTR_TARGET: ["tester1@assert.com"]}
    mock_send.assert_called_once()
    sent_msg = mock_send.call_args.args[0]
    assert sent_msg["To"] == "tester1@assert.com"
    assert sent_msg["Subject"] == "testing"
