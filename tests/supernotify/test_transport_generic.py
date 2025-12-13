from unittest.mock import call

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_ACTION
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_setup_component

from custom_components.supernotify import (
    CONF_DATA,
    CONF_DELIVERY,
    CONF_OPTIONS,
    CONF_TRANSPORT,
    OPTION_DATA_KEYS_EXCLUDE_RE,
    OPTION_DATA_KEYS_INCLUDE_RE,
    OPTION_GENERIC_DOMAIN_STYLE,
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
            service_data={
                ATTR_MESSAGE: "hello there",
                ATTR_TITLE: "testing",
                ATTR_DATA: {"cuteness": "very"},
                ATTR_TARGET: ["weird_generic_1", "weird_generic_2"],
            },
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


async def test_e2e_update_input_text(hass) -> None:
    config = {
        "name": "supernotify",
        "platform": "supernotify",
        "delivery": {"motd": {"transport": "generic", "action": "input_text.set_value"}},
    }
    assert await async_setup_component(hass, "input_text", {"input_text": {"motd": {}}})
    assert await async_setup_component(hass, NOTIFY_DOMAIN, {NOTIFY_DOMAIN: [config]})
    hass.states.async_set("sensor.inside_temperature", "15")
    hass.states.async_set("sensor.outside_temperature", "20")
    await hass.async_block_till_done()

    await async_call_from_config(
        hass,
        {
            "service": "notify.supernotify",
            "data": """{
                "message": "Outside is {{states('sensor.outside_temperature')}}C",
                "data": {"delivery": "motd"},
                "target": "input_text.motd"
            }""",
        },
        blocking=True,
    )
    notification = await hass.services.async_call(
        "supernotify", "enquire_last_notification", None, blocking=True, return_response=True
    )
    assert notification is not None
    assert len(notification["delivered_envelopes"][0]["calls"]) == 1
    assert notification["delivered_envelopes"][0]["calls"][0]["domain"] == "input_text"
    assert notification["delivered_envelopes"][0]["calls"][0]["action"] == "set_value"
    assert notification["delivered_envelopes"][0]["calls"][0]["action_data"] == {"value": "Outside is 20C"}
    assert notification["delivered_envelopes"][0]["calls"][0]["target_data"] == {"entity_id": ["input_text.motd"]}


async def test_update_fixed_message(mock_hass) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "noticeboard": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "text.set_value",
                CONF_DATA: {"value": "Alert Level 3"},
            }
        },
    )
    await uut.initialize()
    await uut.async_send_message(message="", target="text.esp_display")

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "text",
        "set_value",
        service_data={"message": "", "value": "Alert Level 3", "target": "text.esp_display"},
        blocking=False,
        target=None,
        context=None,
        return_response=False,
    )


async def test_update_equiv_domain(mock_hass) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "noticeboard": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "text.set_value",
                CONF_OPTIONS: {OPTION_GENERIC_DOMAIN_STYLE: "input_text"},
            }
        },
    )
    await uut.initialize()
    await uut.async_send_message(message="Alert Level 2", target="text.esp_display")

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "text",
        "set_value",
        service_data={"value": "Alert Level 2"},
        blocking=False,
        target={"entity_id": ["text.esp_display"]},
        context=None,
        return_response=False,
    )


def test_prune_fields(mock_context):
    uut = GenericTransport(mock_context)
    sample = {"foo": 123, "bar": 789, "enabled": True}
    assert (
        uut.prune_data(
            sample,
            "testing",
            Delivery(
                "",
                {CONF_OPTIONS: {OPTION_DATA_KEYS_INCLUDE_RE: ["f.*"], OPTION_DATA_KEYS_EXCLUDE_RE: ["enabled", ".*oo"]}},
                uut,
            ),
        )
        == {}
    )
    assert uut.prune_data(sample, "testing", Delivery("", {CONF_OPTIONS: {OPTION_DATA_KEYS_INCLUDE_RE: ["f.*"]}}, uut)) == {
        "foo": 123
    }
    assert uut.prune_data(sample, "testing", Delivery("", {CONF_OPTIONS: {OPTION_DATA_KEYS_EXCLUDE_RE: ["enabled"]}}, uut)) == {
        "foo": 123,
        "bar": 789,
    }

    assert (
        uut.prune_data(
            None,
            "testing",
            Delivery("", {CONF_OPTIONS: {OPTION_DATA_KEYS_INCLUDE_RE: ["f.*"], OPTION_DATA_KEYS_EXCLUDE_RE: ["enabled"]}}, uut),
        )
        is None
    )

    assert uut.prune_data({"duration": 1.0, "foo": 123}, "siren", Delivery("", {}, uut)) == {"duration": 1.0}
