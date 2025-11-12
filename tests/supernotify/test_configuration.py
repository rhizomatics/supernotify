from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry

from custom_components.supernotify import CONF_DELIVERY_DEFAULTS, CONF_PERSON, CONF_RECIPIENTS, CONF_TARGET, CONF_TRANSPORT
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import PeopleRegistry

from .doubles_lib import DummyTransport
from .hass_setup_lib import TestingContext, register_mobile_app


async def test_default_recipients() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.new_home_owner", CONF_TARGET: "dummy.1"}, {CONF_PERSON: "person.bidey_in"}],
        deliveries={"testing": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(context)
    await uut.initialize()
    await uut.deliver()
    dummy: DummyTransport = cast("DummyTransport", context.delivery_registry.transports["dummy"])
    assert dummy.test_calls[0].target.entity_ids == ["dummy.1"]


async def test_default_recipients_with_override() -> None:
    context = TestingContext(
        recipients=[{CONF_PERSON: "person.new_home_owner", CONF_TARGET: "dummy.1"}, {CONF_PERSON: "person.bidey_in"}],
        deliveries={"testing": {CONF_TRANSPORT: "dummy"}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(context, "testing", action_data={CONF_RECIPIENTS: ["person.new_home_owner"]})
    await uut.initialize()
    await uut.deliver()
    dummy: DummyTransport = cast("DummyTransport", context.delivery_registry.transports["dummy"])
    assert dummy.test_calls[0].target.entity_ids == ["dummy.1"]


async def test_delivery_override_transport() -> None:
    context = TestingContext(
        deliveries={
            "quiet_alert": {
                "transport": "dummy",
                "target": ["switch.pillow_vibrate"],
                "selection": "explicit",
            },
            "regular_alert": {"transport": "dummy", "target": ["switch.pillow_vibrate"], "selection": ["explicit"]},
            "day_alert": {"transport": "dummy", "selection": ["explicit"]},
        },
        transport_configs={"dummy": {CONF_DELIVERY_DEFAULTS: {"target": ["media_player.hall"]}}},
        transport_types=[DummyTransport],
    )
    await context.test_initialize()

    uut = Notification(
        context,
        "testing explicit target in notification call",
        action_data={"delivery": ["regular_alert"]},
        target=["switch.gong"],
    )
    await uut.initialize()
    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["switch.gong"]

    uut = Notification(context, "testing target specified in delivery config", action_data={"delivery": ["quiet_alert"]})
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["switch.pillow_vibrate"]

    uut = Notification(context, "testing defaulting to transport defaults", action_data={"delivery": ["day_alert"]})
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["media_player.hall"]


def test_autoresolve_mobile_devices_for_no_devices(hass: HomeAssistant) -> None:
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    uut = PeopleRegistry([], hass_api)
    uut.initialize()
    assert uut.mobile_devices_for_person("person.test_user") == []


def test_autoresolve_mobile_devices_for_devices(
    hass: HomeAssistant,
    device_registry: device_registry.DeviceRegistry,
    entity_registry: entity_registry.EntityRegistry,
) -> None:
    hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
    uut = PeopleRegistry([], hass_api)
    uut.initialize()
    device = register_mobile_app(uut, person="person.test_user", device_name="phone_bob", title="Bobs Phone")
    assert device is not None
    assert uut.mobile_devices_for_person("person.test_user") == [
        {
            "manufacturer": "xUnit",
            "model": "PyTest001",
            "mobile_app_id": "mobile_app_bobs_phone",
            "device_tracker": "device_tracker.mobile_app_phone_bob",
            "device_id": device.id,
            "device_name": "Bobs Phone",
            # "device_labels": set(),
        }
    ]
