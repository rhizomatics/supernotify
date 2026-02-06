from unittest.mock import Mock, call

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_ACTION
from homeassistant.helpers.service import async_call_from_config
from homeassistant.setup import async_setup_component

from custom_components.supernotify.const import (
    CONF_DATA,
    CONF_DELIVERY,
    CONF_OPTIONS,
    CONF_TRANSPORT,
    OPTION_DATA_KEYS_EXCLUDE_RE,
    OPTION_DATA_KEYS_INCLUDE_RE,
    OPTION_DATA_KEYS_SELECT,
    OPTION_GENERIC_DOMAIN_STYLE,
    OPTION_TARGET_CATEGORIES,
    SELECT_EXCLUDE,
    SELECT_INCLUDE,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import SupernotifyAction
from custom_components.supernotify.transports.generic import GenericTransport, customize_data

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
    generic_calls = notification["deliveries"]["motd"]["delivered"][0]["calls"]
    assert len(generic_calls) == 1
    assert generic_calls[0]["domain"] == "input_text"
    assert generic_calls[0]["action"] == "set_value"
    assert generic_calls[0]["action_data"] == {"value": "Outside is 20C"}
    assert generic_calls[0]["target_data"] == {"entity_id": ["input_text.motd"]}


async def test_update_fixed_message(mock_hass) -> None:
    uut = SupernotifyAction(
        mock_hass,
        deliveries={
            "noticeboard": {
                CONF_TRANSPORT: TRANSPORT_GENERIC,
                CONF_ACTION: "text.set_value",
                CONF_DATA: {"message": "Alert Level 3"},
            }
        },
    )
    await uut.initialize()
    await uut.async_send_message(message="ignore this")

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "text",
        "set_value",
        service_data={"message": "Alert Level 3"},
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


def test_prune_fields():
    uut = GenericTransport(Mock())
    sample = {"foo": 123, "bar": 789, "enabled": True}
    delivery = Delivery(
        "",
        {CONF_OPTIONS: {OPTION_DATA_KEYS_INCLUDE_RE: ["f.*"], OPTION_DATA_KEYS_EXCLUDE_RE: ["enabled", ".*oo"]}},
        uut,
    )
    delivery.upgrade_deprecations()
    assert (
        customize_data(
            sample,
            "testing",
            delivery,
        )
        == {}
    )
    assert customize_data(
        {"fee": 123, "foo": 789},
        "testing",
        delivery,
    ) == {"fee": 123}

    assert customize_data(sample, "testing", Delivery("", {CONF_OPTIONS: {OPTION_DATA_KEYS_SELECT: "f.*"}}, uut)) == {
        "foo": 123
    }
    assert customize_data(
        sample, "testing", Delivery("", {CONF_OPTIONS: {OPTION_DATA_KEYS_SELECT: {SELECT_EXCLUDE: ["enabled"]}}}, uut)
    ) == {
        "foo": 123,
        "bar": 789,
    }

    assert (
        customize_data(
            {},
            "testing",
            Delivery(
                "", {CONF_OPTIONS: {OPTION_DATA_KEYS_SELECT: {SELECT_INCLUDE: ["f.*"], SELECT_EXCLUDE: ["enabled"]}}}, uut
            ),
        )
        == {}
    )

    assert customize_data({"duration": 1.0, "foo": 123}, "siren", Delivery("", {}, uut)) == {"duration": 1.0}


async def test_slack_notify() -> None:
    ctx = TestingContext(
        deliveries="""
            slack:
                transport: generic
                action: notify.my_slack_service
                options:
                    target_categories: slack
            """,
        recipients="""
            - person: person.my_user
              delivery:
                slack:
                    target:
                        slack: A20H2AN55DX
    """,
        services={"notify": ["my_slack_service"]},
        transport_types=[GenericTransport],
    )

    await ctx.test_initialize()
    uut = Notification(
        ctx, message="test message", action_data={"delivery": {"slack": {"enabled": True}}}, target="person.my_user"
    )
    await uut.initialize()
    await uut.deliver()

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "notify",
        "my_slack_service",
        service_data={"message": "test message", "target": "A20H2AN55DX"},
        blocking=False,
        target=None,
        context=None,
        return_response=False,
    )


async def test_ntfy_publish() -> None:
    ctx = TestingContext(
        deliveries="""
            ntfy:
                transport: generic
                action: ntfy.publish
                target:
                    - notify.topic_1
                    - notify.topic_2
                    - joe@mctest.org
                    - mary@mctest.org
            """,
        services={"ntfy": ["publish"]},
        transport_types=[GenericTransport],
    )

    await ctx.test_initialize()
    uut = Notification(
        ctx, message="test message", action_data={"delivery": {"ntfy": {"enabled": True}}, "data": {"tags": ["a", "b"]}}
    )
    await uut.initialize()
    await uut.deliver()

    uut.context.hass_api._hass.services.async_call.assert_has_calls(  # type:ignore [union-attr]
        [
            call(
                "ntfy",
                "publish",
                service_data={"message": "test message", "tags": ["a", "b"], "email": "joe@mctest.org"},
                blocking=False,
                target=None,
                context=None,
                return_response=False,
            ),
            call(
                "ntfy",
                "publish",
                service_data={"message": "test message", "tags": ["a", "b"], "email": "mary@mctest.org"},
                blocking=False,
                target=None,
                context=None,
                return_response=False,
            ),
            call(
                "ntfy",
                "publish",
                service_data={"message": "test message", "tags": ["a", "b"], "entity_id": ["notify.topic_1", "notify.topic_2"]},
                blocking=False,
                target={"entity_id": ["notify.topic_1", "notify.topic_2"]},
                context=None,
                return_response=False,
            ),
        ]
    )


async def test_raw() -> None:
    ctx = TestingContext(
        deliveries="""
            disco:
                transport: generic
                action: light.turn_on
                options:
                    raw: true
                target:
                    - light.disco_1
            """,
        services={"light": ["turn_on"]},
        transport_types=[GenericTransport],
    )

    await ctx.test_initialize()
    uut = Notification(ctx, message="test message", action_data={"delivery": "disco", "data": {"strobe_period": 10}})
    await uut.initialize()
    await uut.deliver()

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "light",
        "turn_on",
        service_data={"message": "test message", "strobe_period": 10, "target": "light.disco_1"},
        blocking=False,
        target=None,
        context=None,
        return_response=False,
    )


async def test_script_turn_on() -> None:
    ctx = TestingContext(
        deliveries="""
            customize:
                transport: generic
                action: script.turn_on
                target: script.dazzle
            """,
        services={"script": ["turn_on"]},
        transport_types=[GenericTransport],
    )

    await ctx.test_initialize()
    uut = Notification(ctx, message="test message", action_data={"delivery": "customize", "data": {"strobe_period": 10}})
    await uut.initialize()
    await uut.deliver()

    uut.context.hass_api._hass.services.async_call.assert_called_once_with(  # type:ignore [union-attr]
        "script",
        "turn_on",
        service_data={"variables": {"message": "test message", "strobe_period": 10}, "entity_id": ["script.dazzle"]},
        blocking=False,
        target={"entity_id": ["script.dazzle"]},
        context=None,
        return_response=False,
    )
