from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.const import CONF_ACTION, CONF_DEFAULT, CONF_METHOD, CONF_NAME

from custom_components.supernotify import CONF_DATA, CONF_DELIVERY, CONF_OPTIONS, METHOD_GENERIC
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery_method import OPTION_TARGET_CATEGORIES
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.generic import GenericDeliveryMethod
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification


async def test_deliver(mock_hass, mock_people_registry) -> None:  # type: ignore
    context = Context()
    uut = GenericDeliveryMethod(
        mock_hass,
        context,
        mock_people_registry,
        {
            "teleport": {
                CONF_METHOD: METHOD_GENERIC,
                CONF_NAME: "teleport",
                CONF_ACTION: "notify.teleportation",
                CONF_DEFAULT: True,
                CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: ["other_id"]},
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
                mock_people_registry,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"teleport": {CONF_DATA: {"cuteness": "very"}}}},
            ),
            target=Target(["weird_generic_1", "weird_generic_2"]),
        )
    )
    mock_hass.services.async_call.assert_called_with(
        "notify",
        "teleportation",
        service_data={
            ATTR_MESSAGE: "hello there",
            ATTR_TITLE: "testing",
            ATTR_DATA: {"cuteness": "very"},
            ATTR_TARGET: ["weird_generic_1", "weird_generic_2"],
        },
    )


async def test_not_notify_deliver(mock_hass, mock_people_registry) -> None:  # type: ignore
    context = Context()
    await context.initialize()
    uut = GenericDeliveryMethod(
        mock_hass,
        context,
        mock_people_registry,
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
                mock_people_registry,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"broker": {CONF_DATA: {"topic": "testing/123", "payload": "boo"}}}},
            ),
            target=Target(["weird_generic_1", "weird_generic_2"]),
        )
    )
    mock_hass.services.async_call.assert_called_with("mqtt", "publish", service_data={"topic": "testing/123", "payload": "boo"})
