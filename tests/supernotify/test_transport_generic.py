from unittest.mock import call

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.const import CONF_ACTION

from custom_components.supernotify import (
    CONF_DATA,
    CONF_DELIVERY,
    CONF_OPTIONS,
    CONF_TRANSPORT,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import SupernotifyAction
from custom_components.supernotify.transports.generic import GenericTransport

from .hass_setup_lib import TestingContext


async def test_deliver() -> None:
    context = TestingContext(
        deliveries={
            "teleport": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "notify.teleportation",
                CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: ["_UNKNOWN_"]},
            }
        }
    )

    uut = GenericTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("teleport", context.delivery_config("teleport"), uut),
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"teleport": {CONF_DATA: {"cuteness": "very"}}}},
            ),
            target=Target(["weird_generic_1", "weird_generic_2"]),
        )
    )
    context.hass.services.async_call.assert_has_calls([  # type: ignore
        call(
            "notify",
            "teleportation",
            service_data={ATTR_MESSAGE: "hello there",
                        ATTR_TITLE: "testing",
                        ATTR_DATA: {"cuteness": "very"},
                        ATTR_TARGET: ["weird_generic_1", "weird_generic_2"]},
            blocking=False,
            context=None,
            target=None,
            return_response=False,
        )
    ])


async def test_not_notify_deliver() -> None:
    context = TestingContext(deliveries={"broker": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "mqtt.publish"}})

    uut = GenericTransport(context)
    await context.test_initialize(transport_instances=[uut])
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("broker", context.delivery_config("broker"), uut),
            Notification(
                context,
                message="hello there",
                title="testing",
                action_data={CONF_DELIVERY: {"broker": {CONF_DATA: {"topic": "testing/123", "payload": "boo"}}}},
            ),
            target=Target(["weird_generic_1", "weird_generic_2"]),
        )
    )
    context.hass.services.async_call.assert_called_with(  # type: ignore
        "mqtt",
        "publish",
        service_data={"topic": "testing/123", "payload": "boo"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_update_input_text(mock_hass) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "noticeboard": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "input_text.set_value",
            }
        },
    )
    await uut.initialize()
    await uut.async_send_message(message="Display on Screen", target="input_text.esp_display")

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "input_text",
        "set_value",
        service_data={"value": "Display on Screen"},
        target={"entity_id": ["input_text.esp_display"]},
        blocking=False,
        context=None,
        return_response=False,
    )


async def test_update_fixed_message(mock_hass) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "noticeboard": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "text.set_value",
                CONF_DATA: {"value": "Alert Level 3"}
            }
        },
    )
    await uut.initialize()
    await uut.async_send_message(message=None, target="text.esp_display")

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "text",
        "set_value",
        service_data={"value": "Alert Level 3", "target": "text.esp_display"},
        blocking=False,
        target=None,
        context=None,
        return_response=False,
    )
