from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACTION, CONF_DEFAULT, CONF_METHOD, CONF_NAME

from custom_components.supernotify import CONF_DATA, CONF_DELIVERY, METHOD_GENERIC
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.generic import GenericDeliveryMethod
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass) -> None:  # type: ignore
    context = Context()
    uut = GenericDeliveryMethod(
        mock_hass,
        context,
        {
            "teleport": {
                CONF_METHOD: METHOD_GENERIC,
                CONF_NAME: "teleport",
                CONF_ACTION: "notify.teleportation",
                CONF_DEFAULT: True,
            }
        },
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "teleport",
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"teleport": {CONF_DATA: {"cuteness": "very"}}}},
            ),
            targets=["weird_generic_1", "weird_generic_2"],
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "teleportation",
        service_data={ATTR_TITLE: "testing", ATTR_MESSAGE: "hello there", ATTR_DATA: {"cuteness": "very"}},
        target={
            ATTR_ENTITY_ID: ["weird_generic_1", "weird_generic_2"],
        },
    )


async def test_not_notify_deliver(mock_hass) -> None:  # type: ignore
    context = Context()
    await context.initialize()
    uut = GenericDeliveryMethod(
        mock_hass,
        context,
        {"broker": {CONF_METHOD: METHOD_GENERIC, CONF_NAME: "broker", CONF_ACTION: "mqtt.publish", CONF_DEFAULT: True}},
    )
    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.deliver(
        Envelope(
            "broker",
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"broker": {CONF_DATA: {"topic": "testing/123", "payload": "boo"}}}},
            ),
            targets=["weird_generic_1", "weird_generic_2"],
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "mqtt",
        "publish",
        service_data={"topic": "testing/123", "payload": "boo"},
        target={"entity_id": ["weird_generic_1", "weird_generic_2"]},
    )
