from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry

from custom_components.supernotify import CONF_PERSON, CONF_RECIPIENTS
from custom_components.supernotify.context import HomeAssistantAccess
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import ScenarioRegistry

from .doubles_lib import DummyTransport
from .hass_setup_lib import register_mobile_app


async def test_default_recipients(uninitialized_superconfig, mock_hass, mock_hass_access, mock_people_registry) -> None:  # type: ignore
    context = uninitialized_superconfig
    context._recipients = [{CONF_PERSON: "person.new_home_owner"}, {CONF_PERSON: "person.bidey_in"}]

    dummy = DummyTransport(mock_hass, context, mock_people_registry, {})
    context.configure_for_tests(transport_instances=[dummy], create_default_scenario=True)
    await context.initialize()
    context.scenario_registry = ScenarioRegistry({})
    await context.scenario_registry.initialize(context.deliveries, context.default_deliveries, {}, mock_hass)

    uut = Notification(context, mock_people_registry)
    await uut.initialize()
    await uut.deliver()
    assert dummy.test_calls == [Envelope("dummy", uut, target=Target(["dummy.new_home_owner", "dummy.bidey_in"]))]


async def test_default_recipients_with_override(uninitialized_superconfig, mock_hass, mock_people_registry) -> None:  # type: ignore
    context = uninitialized_superconfig
    context._recipients = [{CONF_PERSON: "person.new_home_owner"}, {CONF_PERSON: "person.bidey_in"}]

    dummy = DummyTransport(mock_hass, context, mock_people_registry, {})
    context.configure_for_tests(transport_instances=[dummy], create_default_scenario=True)
    await context.initialize()
    context.scenario_registry = ScenarioRegistry({})
    await context.scenario_registry.initialize(context.deliveries, context.default_deliveries, {}, mock_hass)

    uut = Notification(context, mock_people_registry, "testing", action_data={CONF_RECIPIENTS: ["person.new_home_owner"]})
    await uut.initialize()
    await uut.deliver()
    assert dummy.test_calls == [Envelope("dummy", uut, target=Target(["dummy.new_home_owner"]))]


async def test_delivery_override_transport(uninitialized_superconfig, mock_hass, mock_people_registry) -> None:  # type: ignore
    delivery_config = {
        "quiet_alert": {
            "transport": "dummy",
            "target": ["switch.pillow_vibrate"],
            "selection": "explicit",
        },
        "regular_alert": {"transport": "dummy", "target": ["switch.pillow_vibrate"], "selection": ["explicit"]},
        "day_alert": {"transport": "dummy", "selection": ["explicit"]},
    }
    context = uninitialized_superconfig
    context._deliveries = delivery_config
    dummy = DummyTransport(
        mock_hass, context, mock_people_registry, delivery_config, delivery_defaults={"target": ["media_player.hall"]}
    )
    context.configure_for_tests(transport_instances=[dummy], create_default_scenario=True)
    await context.initialize()

    uut = Notification(
        context,
        mock_people_registry,
        "testing explicit target in notification call",
        action_data={"delivery": ["regular_alert"]},
        target=["switch.gong"],
    )
    await uut.initialize()
    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["switch.gong"]

    uut = Notification(
        context, mock_people_registry, "testing target specified in delivery config", action_data={"delivery": ["quiet_alert"]}
    )
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["switch.pillow_vibrate"]

    uut = Notification(
        context, mock_people_registry, "testing defaulting to transport defaults", action_data={"delivery": ["day_alert"]}
    )
    await uut.initialize()

    await uut.deliver()
    envelope = uut.delivered_envelopes[0]
    assert envelope.target.entity_ids == ["media_player.hall"]


def test_autoresolve_mobile_devices_for_no_devices(hass: HomeAssistant) -> None:
    hass_access: HomeAssistantAccess = HomeAssistantAccess(hass)
    uut = PeopleRegistry([], hass_access)
    uut.initialize()
    assert uut.mobile_devices_for_person("person.test_user") == []


def test_autoresolve_mobile_devices_for_devices(
    hass: HomeAssistant,
    device_registry: device_registry.DeviceRegistry,
    entity_registry: entity_registry.EntityRegistry,
) -> None:
    hass_access: HomeAssistantAccess = HomeAssistantAccess(hass)
    uut = PeopleRegistry([], hass_access)
    uut.initialize()
    device = register_mobile_app(uut, person="person.test_user", device_name="phone_bob", title="Bobs Phone")
    assert device is not None
    assert uut.mobile_devices_for_person("person.test_user") == [
        {
            "manufacturer": "xUnit",
            "model": "PyTest001",
            "notify_action": "mobile_app_bobs_phone",
            "device_tracker": "device_tracker.mobile_app_phone_bob",
            "device_id": device.id,
            "device_name": "Bobs Phone",
            # "device_labels": set(),
        }
    ]
