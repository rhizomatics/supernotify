from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

from homeassistant.const import CONF_ACTION, CONF_TARGET
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry
from custom_components.supernotify import (
    CONF_METHOD,
    CONF_SELECTION,
    METHOD_ALEXA,
    METHOD_ALEXA_MEDIA_PLAYER,
    METHOD_CHIME,
    METHOD_EMAIL,
    METHOD_GENERIC,
    METHOD_PERSISTENT,
    METHOD_SMS,
    SELECTION_BY_SCENARIO,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.methods.generic import GenericDeliveryMethod

from .hass_setup_lib import register_device

DELIVERY: dict[str, Any] = {
    "email": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_METHOD: METHOD_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_METHOD: METHOD_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_devices": {CONF_METHOD: METHOD_ALEXA, CONF_ACTION: "notify.send_message"},
    "alexa_media_player": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_METHOD: METHOD_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_METHOD: METHOD_PERSISTENT, CONF_SELECTION: SELECTION_BY_SCENARIO},
}


async def test_simple_create(hass: HomeAssistant) -> None:
    context = Mock(Context)
    uut = GenericDeliveryMethod(hass, context, DELIVERY)
    await uut.initialize()
    assert list(uut.valid_deliveries.keys()) == [d for d, dc in DELIVERY.items() if dc[CONF_METHOD] == METHOD_GENERIC]
    assert uut.default_delivery is not None
    assert uut.default_delivery.name == "DEFAULT_generic"


async def test_default_delivery_defaulted(hass: HomeAssistant) -> None:
    context = Mock(Context)

    uut = GenericDeliveryMethod(hass, context, DELIVERY, delivery_defaults={CONF_ACTION: "notify.slackity"})
    await uut.initialize()
    assert uut.default_delivery is not None
    assert uut.default_delivery.action == "notify.slackity"
    assert list(uut.valid_deliveries.keys()) == ["chat"]


async def test_method_defaults_used_for_missing_service(hass: HomeAssistant) -> None:
    delivery = {"chatty": {CONF_METHOD: METHOD_GENERIC, CONF_TARGET: ["chan1", "chan2"]}}
    context = Context(deliveries=delivery)
    uut = GenericDeliveryMethod(hass, context, delivery, delivery_defaults={CONF_ACTION: "notify.slackity"})
    context.configure_for_tests(method_instances=[uut])
    await context.initialize()

    await uut.initialize()
    assert list(uut.valid_deliveries.keys()) == ["chatty"]
    assert uut.valid_deliveries["chatty"].action == "notify.slackity"


def test_simplify_text() -> None:
    from custom_components.supernotify.methods.generic import GenericDeliveryMethod

    uut = GenericDeliveryMethod(None, None, {})
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
    uut = GenericDeliveryMethod(hass, ctx, {}, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target.device_id == []

    dev: DeviceEntry | None = register_device(ctx)
    assert dev is not None
    uut = GenericDeliveryMethod(hass, ctx, {}, device_domain=["unit_testing"], device_discovery=True)
    await uut.initialize()
    assert uut.delivery_defaults.target.device_id == [dev.id]
