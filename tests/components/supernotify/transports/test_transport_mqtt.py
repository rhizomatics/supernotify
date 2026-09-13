from homeassistant.const import (
    CONF_NAME,
)

from custom_components.supernotify.const import CONF_DATA, CONF_INCLUSION, CONF_TRANSPORT, INCLUSION_DEFAULT, TRANSPORT_MQTT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.mqtt import MQTTTransport
from tests.components.supernotify.hass_setup_lib import TestingContext


async def test_deliver(mock_hass, mock_scenario_registry, uninitialized_unmocked_config) -> None:  # type: ignore
    deliveries = {
        "dive_dive_dive": {
            CONF_TRANSPORT: TRANSPORT_MQTT,
            CONF_NAME: "dive_dive_dive",
            CONF_DATA: {
                "topic": "zigbee2mqtt/Downstairs Siren/set",
                "payload": {
                    "warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}
                },
            },
            CONF_INCLUSION: [INCLUSION_DEFAULT],
        }
    }
    context = uninitialized_unmocked_config
    context.delivery_registry._config_deliveries = deliveries
    context.scenario_registry = mock_scenario_registry

    uut = MQTTTransport(context)

    await uut.initialize()
    context.configure_for_tests([uut])
    await context.initialize()
    await context.delivery_registry.initialize(context)

    notification = Notification(context, message="Will be ignored", title="Also Ignored")
    await notification.initialize()
    await notification.deliver()

    context.hass_api.call_service.assert_called_with(
        "mqtt",
        "publish",
        service_data={
            "topic": "zigbee2mqtt/Downstairs Siren/set",
            "payload": '{"warning": {"duration": 30, "mode": "emergency", "level": "low", "strobe": "true", "strobe_duty_cycle": 10}}',
        },
        debug=False,
        context=None,
    )


def test_recipient_target_returns_none(mock_hass, uninitialized_unmocked_config) -> None:  # type: ignore
    uut = MQTTTransport(uninitialized_unmocked_config)
    result = uut.recipient_target({"person": "person.test"})
    assert result is None


async def test_deliver_warns_on_missing_topic() -> None:
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_DATA: {"payload": "hello"},
            }
        }
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MQTT)
    n = Notification(ctx, message="ignored")
    await n.initialize()
    envelope = Envelope(
        Delivery("broker", ctx.delivery_config("broker"), uut),
        n,
        data={"payload": "hello"},
    )
    await uut.deliver(envelope)


async def test_deliver_topic_as_target() -> None:
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
            }
        }
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MQTT)
    n = Notification(ctx, message="ignored")
    await n.initialize()
    envelope = Envelope(
        Delivery("broker", ctx.delivery_config("broker"), uut),
        n,
        target=Target("notify/queue/1"),
        data={"payload": {"warning": "on"}},
    )
    result = await uut.deliver(envelope)

    assert result is True
    ctx.hass.services.async_call.assert_called_with(  # type:ignore
        "mqtt",
        "publish",
        service_data={"payload": '{"warning": "on"}', "topic": "notify/queue/1"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_multiple_topics_as_target() -> None:
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
            }
        }
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MQTT)
    n = Notification(ctx, message="ignored")
    await n.initialize()
    envelope = Envelope(
        Delivery("broker", ctx.delivery_config("broker"), uut),
        n,
        target=Target(["notify/queue/1", "notify/queue/2"]),
        data={"payload": {"warning": "on"}},
    )
    result = await uut.deliver(envelope)

    assert result is True
    assert ctx.hass.services.async_call.call_count == 2  # type:ignore


async def test_deliver_ignores_other_transport_targets_in_blended_list() -> None:
    """A notification-level target list mixing categories must not leak email/phone/etc

    into mqtt topics - only the `topic:`-prefixed entry should be published to. A prefix is
    always a target category (never a transport or delivery name directly - see
    `test_deliver_dict_mapping_scopes_to_custom_delivery_name` for delivery-name mapping).

    This has to go through `Notification.deliver()` rather than constructing an `Envelope`
    directly: the scoping happens in `Delivery.select_targets()` (via `target_categories`
    on the mqtt transport), which only runs as part of the full target-resolution pipeline.
    """
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            }
        }
    )
    await ctx.test_initialize()
    n = Notification(
        ctx,
        message="ignored",
        target=["me@house.org", "+48323232211", "discord_channel:9585", "topic:my/topic/name"],
    )
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_once_with(  # type:ignore
        "mqtt",
        "publish",
        service_data={"payload": "ignored", "topic": "my/topic/name"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_dict_mapping_scopes_to_custom_delivery_name() -> None:
    """A `target: {delivery_name: value}` mapping reaches a custom-named delivery precisely,

    while a `target: {mqtt: value}` mapping (the transport's own name) still reaches every
    mqtt delivery, letting scenario/time/occupancy selection logic decide which one fires -
    so with a default `mqtt` delivery and a custom-named `broker` delivery both configured,
    `broker` sees both topics but the default `mqtt` delivery only sees the transport-wide one.
    """
    ctx = TestingContext(
        deliveries={
            TRANSPORT_MQTT: {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
        }
    )
    await ctx.test_initialize()
    n = Notification(
        ctx,
        message="ignored",
        target={"mqtt": "any/topic", "broker": "specific/topic"},
    )
    await n.initialize()
    await n.deliver()

    calls = ctx.hass.services.async_call.call_args_list  # type:ignore
    topics_published = sorted(call.kwargs["service_data"]["topic"] for call in calls)
    assert topics_published == ["any/topic", "any/topic", "specific/topic"]


async def test_deliver_topic_category_mapping() -> None:
    """`target: {topic: value}` is a dedicated, unambiguous category for mqtt topics -

    distinct from overloading the transport's own name (`mqtt:`) or a delivery's name.
    """
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            }
        }
    )
    await ctx.test_initialize()
    n = Notification(ctx, message="hello", target={"topic": "clean/category/name"})
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_once_with(  # type:ignore
        "mqtt",
        "publish",
        service_data={"payload": "hello", "topic": "clean/category/name"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )


async def test_deliver_action_level_delivery_override_bare_target() -> None:
    """A bare, unqualified target set via `data: {delivery: {<name>: {target: ...}}}` on

    the notify action itself is reclassified into mqtt's `topic` category the same way a
    delivery's own YAML-configured `target:` is - this exercises the delivery_override
    wiring in `Notification.generate_targets()`, not `Delivery.__init__`.
    """
    ctx = TestingContext(
        deliveries={
            "broker": {
                CONF_TRANSPORT: TRANSPORT_MQTT,
            }
        }
    )
    await ctx.test_initialize()
    n = Notification(
        ctx,
        message="hello",
        action_data={"delivery": {"broker": {"target": "notify/queue/1"}}},
    )
    await n.initialize()
    await n.deliver()

    ctx.hass.services.async_call.assert_called_once_with(  # type:ignore
        "mqtt",
        "publish",
        service_data={"payload": "hello", "topic": "notify/queue/1"},
        blocking=False,
        context=None,
        target=None,
        return_response=False,
    )
