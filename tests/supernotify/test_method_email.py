from pathlib import Path

from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_EMAIL
from pytest_unordered import unordered

from custom_components.supernotify import ATTR_DATA, ATTR_DELIVERY, CONF_PERSON, CONF_TEMPLATE, CONF_TRANSPORT, TRANSPORT_EMAIL
from custom_components.supernotify.context import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.email import EmailTransport


async def test_deliver(mock_hass, mock_people_registry) -> None:  # type: ignore
    """Test on_notify_email."""
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])
    delivery_config = {"plain_email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}}
    await context.initialize()
    uut = EmailTransport(mock_hass, context, mock_people_registry, delivery_config)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()

    await uut.deliver(
        Envelope(
            "plain_email",
            Notification(
                context,
                mock_people_registry,
                message="hello there",
                title="testing",
                action_data={ATTR_DELIVERY: {"plain_email": {ATTR_DATA: {"footer": "pytest"}}}},
            ),
            target=Target(["tester1@assert.com"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smtp",
        service_data={"target": ["tester1@assert.com"], "title": "testing", "message": "hello there\n\npytest"},
    )


async def test_deliver_with_template(mock_hass, mock_people_registry) -> None:  # type: ignore
    context = Context(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        template_path="tests/supernotify/fixtures/templates",
    )
    delivery_config = {
        "default": {
            CONF_TRANSPORT: TRANSPORT_EMAIL,
            CONF_ACTION: "notify.smtp",
            CONF_TEMPLATE: "minimal_test.html.j2",
            CONF_DEFAULT: True,
        }
    }
    uut = EmailTransport(mock_hass, context, mock_people_registry, delivery_config)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "default",
            Notification(context, mock_people_registry, message="hello there", title="testing"),
            target=Target(["tester9@assert.com"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smtp",
        service_data={
            "target": ["tester9@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"html": "<H1>testing</H1>"},
        },
    )


async def test_deliver_with_preformatted_html(mock_hass, mock_people_registry) -> None:  # type: ignore
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])

    uut = EmailTransport(
        mock_hass,
        context,
        mock_people_registry,
        {"default": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}},
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    notification = Notification(
        context,
        mock_people_registry,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={"message_html": "<H3>testing</H3>", "delivery": {"default": {"data": {"footer": ""}}}},
    )
    await notification.initialize()
    await uut.deliver(Envelope("default", notification, target=Target(["tester9@assert.com"])))
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smtp",
        service_data={
            "target": ["tester9@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"html": "<H3>testing</H3>"},
        },
    )


async def test_deliver_with_preformatted_html_and_image(mock_hass, mock_people_registry) -> None:  # type: ignore
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])

    uut = EmailTransport(
        mock_hass,
        context,
        mock_people_registry,
        {"default": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}},
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    notification = Notification(
        context,
        mock_people_registry,
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
    notification.snapshot_image_path = Path("/local/picture.jpg")
    await uut.deliver(Envelope("default", notification, target=Target(notification.target)))
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smtp",
        service_data={
            "target": ["tester9@assert.com"],
            "title": "testing",
            "message": "hello there",
            "data": {"images": ["/local/picture.jpg"], "html": '<H3>testing</H3><div><p><img src="cid:picture.jpg"></p></div>'},
        },
    )


def test_good_email_addresses(mock_hass, mock_people_registry):  # type: ignore
    """Test good email addresses."""
    uut = EmailTransport(mock_hass, Context(), mock_people_registry, {})
    assert uut.select_targets(
        Target([
            "test421@example.com",
            "t@example.com",
            "t.1.g@example.com",
            "test-hyphen+ext@example.com",
            "test@sub.topsub.example.com",
            "test+fancy_rules@example.com",
        ])
    ).email == unordered([
        "test421@example.com",
        "t@example.com",
        "t.1.g@example.com",
        "test-hyphen+ext@example.com",
        "test@sub.topsub.example.com",
        "test+fancy_rules@example.com",
    ])


def test_bad_email_addresses(mock_hass, mock_people_registry):  # type: ignore
    """Test good email addresses."""
    uut = EmailTransport(mock_hass, Context(), mock_people_registry, {})

    assert (
        uut.select_targets(Target(["test@example@com", "sub.topsub.example.com", "test+fancy_rules@com", "", "@", "a@b"])).email
        == []
    )
