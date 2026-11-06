from typing import Any

from homeassistant.components.notify import NotifyEntity
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_ACTION
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_unordered import unordered

from custom_components.supernotify.const import CONF_TRANSPORT, TRANSPORT_ALEXA
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.alexa_devices import AlexaDevicesTransport
from tests.components.supernotify.hass_setup_lib import TestingContext
from tests.components.supernotify.transports.schema_usage import SchemaCase, assert_schema_usage, sizes

DELIVERY = {
    "alexa_devices": {CONF_TRANSPORT: TRANSPORT_ALEXA, CONF_ACTION: "notify.send_message"},
}


async def test_notify_alexa(mock_hass, unmocked_config) -> None:  # type: ignore
    """Test on_notify_alexa."""
    context = unmocked_config

    uut = AlexaDevicesTransport(context)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("default", {}, uut),
            Notification(context, message="hello there"),
            target=Target(["notify.bedroom_echo_announce"]),
        )
    )
    unmocked_config.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "hello there"},
        target={
            "entity_id": ["notify.bedroom_echo_announce"],
        },
        debug=False,
        context=None,
    )


async def test_notify_alexa_with_title(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config

    uut = AlexaDevicesTransport(context)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("default", {}, uut),
            Notification(context, message="hello there", title="Dinner"),
            target=Target(["notify.bedroom_echo_announce"]),
        )
    )
    unmocked_config.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "hello there", "title": "Dinner"},
        target={
            "entity_id": ["notify.bedroom_echo_announce"],
        },
        debug=False,
        context=None,
    )


async def test_notify_alexa_title_spoken_without_message(mock_hass, unmocked_config) -> None:  # type: ignore
    context = unmocked_config

    uut = AlexaDevicesTransport(context)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    await uut.deliver(
        Envelope(
            Delivery("default", {}, uut),
            Notification(context, message="", title="Dinner"),
            target=Target(["notify.bedroom_echo_speak"]),
        )
    )
    unmocked_config.hass_api.call_service.assert_called_with(
        "notify",
        "send_message",
        service_data={"message": "Dinner", "title": "Dinner"},
        target={
            "entity_id": ["notify.bedroom_echo_speak"],
        },
        debug=False,
        context=None,
    )


async def test_notify_alexa_title_ignored_before_2026_11(hass: HomeAssistant) -> None:
    """Before Home Assistant 2026.11, an alexa_devices notify entity has no title feature and
    drops a title, so sending one must still deliver the message rather than fail"""

    class PreTitleAlexaNotifyEntity(NotifyEntity):
        # as alexa_devices' AmazonNotifyEntity was in Home Assistant 2026.10
        _attr_name = "Bedroom Echo Announce"
        _attr_unique_id = "bedroom_echo_announce"

        def __init__(self) -> None:
            self.sent: list[str] = []

        async def async_send_message(self, message: str, title: str | None = None, **kwargs: Any) -> None:
            self.sent.append(message)

    assert await async_setup_component(hass, NOTIFY_DOMAIN, {})
    echo = PreTitleAlexaNotifyEntity()
    await hass.data[NOTIFY_DOMAIN].async_add_entities([echo])
    context = TestingContext(homeassistant=hass, deliveries=DELIVERY, viable_transport_types=[AlexaDevicesTransport])
    await context.test_initialize()
    uut = context.transport(TRANSPORT_ALEXA)

    assert await uut.deliver(
        Envelope(
            Delivery("default", {}, uut),
            Notification(context, message="hello there", title="Dinner"),
            target=Target(["notify.bedroom_echo_announce"]),
        )
    )
    await hass.async_block_till_done()

    assert echo.sent == ["hello there"]


async def test_notify_alexa_no_targets(mock_hass, unmocked_config) -> None:
    context = unmocked_config

    uut = AlexaDevicesTransport(context)
    context.configure_for_tests([uut])
    await context.initialize()
    await uut.initialize()

    result = await uut.deliver(
        Envelope(
            Delivery("default", {}, uut),
            Notification(context, message="hello there"),
            target=Target([]),
        )
    )
    assert result is False
    unmocked_config.hass_api.call_service.assert_not_called()


def test_alexa_transport_selects_targets(mock_hass, unmocked_config) -> None:  # type: ignore
    """Targets are selected by registry platform (this integration's own notify
    entities), not by an entity_id naming convention - so a genuine alexa_device entity
    with no "_speak"/"_announce" suffix is still selected, and another integration's
    notify entity (e.g. alexa_media_player) is correctly excluded even if named similarly.
    An HA group target is selected too, since it isn't owned by any platform."""
    platforms = {
        "notify.bedroom_echo_announce": "alexa_devices",
        "notify.living_room_echo_2_speak": "alexa_devices",
        "notify.kitchen_echo": "alexa_devices",
        "notify.alexa_media_player_announce": "alexa_media_player",
    }
    unmocked_config.hass_api.platform_for_entity = lambda entity_id: platforms.get(entity_id)  # type: ignore

    uut = Delivery("unit_testing", {}, AlexaDevicesTransport(unmocked_config, {}))
    assert uut.select_targets(
        Target([
            "switch.alexa_1",
            "media_player.hall_1",
            "notify.bedroom_echo_announce",
            "notify.living_room_echo_2_speak",
            "notify.kitchen_echo",
            "notify.alexa_media_player_announce",
            "group.family_room",
        ])
    ).entity_ids == unordered([
        "notify.living_room_echo_2_speak",
        "notify.bedroom_echo_announce",
        "notify.kitchen_echo",
        "group.family_room",
    ])


@sizes
async def test_schema_usage(hass: HomeAssistant, maximal: bool) -> None:
    case = SchemaCase(
        AlexaDevicesTransport,
        ["notify.kitchen_echo_announce"],
        {"notify.send_message"},
    )
    await assert_schema_usage(hass, case, maximal)
