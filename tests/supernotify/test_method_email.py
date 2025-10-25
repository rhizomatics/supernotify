from pathlib import Path

from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_EMAIL, CONF_METHOD

from custom_components.supernotify import ATTR_DATA, ATTR_DELIVERY, CONF_PERSON, CONF_TEMPLATE, METHOD_EMAIL
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.email import EmailDeliveryMethod
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass) -> None:  # type: ignore
    """Test on_notify_email."""
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])
    delivery_config = {"plain_email": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}}
    await context.initialize()
    uut = EmailDeliveryMethod(mock_hass, context, delivery_config)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()

    await uut.deliver(
        Envelope(
            "plain_email",
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={ATTR_DELIVERY: {"plain_email": {ATTR_DATA: {"footer": "pytest"}}}},
            ),
            targets=["tester1@assert.com"],
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "smtp",
        service_data={"target": ["tester1@assert.com"], "title": "testing", "message": "hello there\n\npytest"},
    )


async def test_deliver_with_template(mock_hass) -> None:  # type: ignore
    context = Context(
        recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}],
        template_path="tests/supernotify/fixtures/templates",
    )
    delivery_config = {
        "default": {
            CONF_METHOD: METHOD_EMAIL,
            CONF_ACTION: "notify.smtp",
            CONF_TEMPLATE: "minimal_test.html.j2",
            CONF_DEFAULT: True,
        }
    }
    uut = EmailDeliveryMethod(mock_hass, context, delivery_config)
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope("default", Notification(context, message="hello there", title="testing"), targets=["tester9@assert.com"])
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


async def test_deliver_with_preformatted_html(mock_hass) -> None:  # type: ignore
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])

    uut = EmailDeliveryMethod(
        mock_hass, context, {"default": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}}
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    notification = Notification(
        context,
        message="hello there",
        title="testing",
        target=["tester9@assert.com"],
        action_data={"message_html": "<H3>testing</H3>", "delivery": {"default": {"data": {"footer": ""}}}},
    )
    await notification.initialize()
    await uut.deliver(Envelope("default", notification, targets=["tester9@assert.com"]))
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


async def test_deliver_with_preformatted_html_and_image(mock_hass) -> None:  # type: ignore
    context = Context(recipients=[{CONF_PERSON: "person.tester1", CONF_EMAIL: "tester1@assert.com"}])

    uut = EmailDeliveryMethod(
        mock_hass, context, {"default": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp", CONF_DEFAULT: True}}
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
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
    notification.snapshot_image_path = Path("/local/picture.jpg")
    await uut.deliver(Envelope("default", notification, targets=notification.target))
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


def test_good_email_addresses(mock_hass):  # type: ignore
    """Test good email addresses."""
    uut = EmailDeliveryMethod(mock_hass, Context(), {})
    assert uut.select_target("test421@example.com")
    assert uut.select_target("t@example.com")
    assert uut.select_target("t.1.g@example.com")
    assert uut.select_target("test-hyphen+ext@example.com")
    assert uut.select_target("test@sub.topsub.example.com")
    assert uut.select_target("test+fancy_rules@example.com")


def test_bad_email_addresses(mock_hass):  # type: ignore
    """Test good email addresses."""
    uut = EmailDeliveryMethod(mock_hass, Context(), {})
    assert not uut.select_target("test@example@com")
    assert not uut.select_target("sub.topsub.example.com")
    assert not uut.select_target("test+fancy_rules@com")
    assert not uut.select_target("")
    assert not uut.select_target("@")
    assert not uut.select_target("a@b")
