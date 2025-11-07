from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

from homeassistant.const import CONF_ACTION, CONF_TARGET
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry
from custom_components.supernotify import (
    CONF_SELECTION,
    CONF_TRANSPORT,
    SELECTION_BY_SCENARIO,
    TRANSPORT_ALEXA,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_EMAIL,
    TRANSPORT_GENERIC,
    TRANSPORT_PERSISTENT,
    TRANSPORT_SMS,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.transports.generic import GenericTransport

from .hass_setup_lib import register_device

DELIVERY: dict[str, Any] = {
    "email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_TRANSPORT: TRANSPORT_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_devices": {CONF_TRANSPORT: TRANSPORT_ALEXA, CONF_ACTION: "notify.send_message"},
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_SELECTION: [SELECTION_BY_SCENARIO]},
}


async def test_simple_create(hass: HomeAssistant, mock_people_registry: PeopleRegistry) -> None:
    context = Mock(Context)
    uut = GenericTransport(hass, context, mock_people_registry, DELIVERY)
    await uut.initialize()
    assert list(uut.valid_deliveries.keys()) == [d for d, dc in DELIVERY.items() if dc[CONF_TRANSPORT] == TRANSPORT_GENERIC]
    assert uut.default_delivery is not None
    assert uut.default_delivery.name == "DEFAULT_generic"


async def test_default_delivery_defaulted(hass: HomeAssistant, mock_people_registry: PeopleRegistry) -> None:
    context = Mock(Context)

    uut = GenericTransport(hass, context, mock_people_registry, DELIVERY, delivery_defaults={CONF_ACTION: "notify.slackity"})
    await uut.initialize()
    assert uut.default_delivery is not None
    assert uut.default_delivery.action == "notify.slackity"
    assert list(uut.valid_deliveries.keys()) == ["chat"]


async def test_transport_defaults_used_for_missing_service(hass: HomeAssistant, mock_people_registry: PeopleRegistry) -> None:
    delivery = {"chatty": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_TARGET: ["chan1", "chan2"]}}
    context = Context(deliveries=delivery)
    uut = GenericTransport(hass, context, mock_people_registry, delivery, delivery_defaults={CONF_ACTION: "notify.slackity"})
    context.configure_for_tests(transport_instancess=[uut])
    await context.initialize()

    await uut.initialize()
    assert list(uut.valid_deliveries.keys()) == ["chatty"]
    assert uut.valid_deliveries["chatty"].action == "notify.slackity"


def test_simplify_text() -> None:
    from custom_components.supernotify.transports.generic import GenericTransport

    uut = GenericTransport(None, None, None, {})
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>", strip_urls=True)
        == "Hello world! Visit it's great 100 test"
    )
    assert (
        uut.simplify("Hello_world! Visit https://example.com (it's great) £100 <test>")
        == "Hello world! Visit https://example.com it's great 100 test"
    )
    assert uut.simplify("NoSpecialChars123") == "NoSpecialChars123"


async def test_device_discovery(hass: HomeAssistant) -> None:
    ctx = Context(hass)
    people_registry = PeopleRegistry(hass, [], ctx.entity_registry(), ctx.device_registry())
    uut = GenericTransport(hass, ctx, people_registry, {}, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target is None

    dev: DeviceEntry | None = register_device(people_registry)
    assert dev is not None
    uut = GenericTransport(hass, ctx, people_registry, {}, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target is not None
    assert uut.delivery_defaults.target.device_ids == [dev.id]
