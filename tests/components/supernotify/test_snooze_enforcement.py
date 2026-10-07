from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Context, Event

from custom_components.supernotify.const import ATTR_ACTION
from custom_components.supernotify.model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from custom_components.supernotify.snoozer import Snoozer
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

YAML = """
  name: Supernotify
  platform: supernotify
  delivery:
    email:
      transport: email
      action: notify.smtp
      target: joe@mctest.org
"""


async def _send(ctx: TestingContext, message: str, camera_entity_id: str | None = None) -> Notification:
    action_data = {"media": {"camera_entity_id": camera_entity_id}} if camera_entity_id else None
    uut = Notification(ctx, message=message, action_data=action_data)
    await uut.initialize()
    await uut.deliver()
    return uut


def _delivered(uut: Notification) -> bool:
    return EnvelopeOutcome.SUCCESS in uut.deliveries.get("email", {})


async def test_everyone_delivery_snooze_suppresses_delivery(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, yaml=YAML, services={"notify": ["smtp"]})
    await ctx.test_initialize()
    ctx.snoozer.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_email"}))

    assert not _delivered(await _send(ctx, "Something happened"))


async def test_everyone_camera_snooze_only_suppresses_that_camera(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, yaml=YAML, services={"notify": ["smtp"]})
    await ctx.test_initialize()
    ctx.snoozer.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_camera.yard"})
    )

    assert not _delivered(await _send(ctx, "Person in the yard", camera_entity_id="camera.yard"))
    assert _delivered(await _send(ctx, "Person on the porch", camera_entity_id="camera.porch"))
    assert _delivered(await _send(ctx, "No camera involved"))


async def test_everyone_tag_snooze_matches_data_entity_id_or_camera(hass: HomeAssistant) -> None:
    hass.states.async_set("camera.driveway", "idle", {"friendly_name": "Driveway mainStream"})
    ctx = TestingContext(homeassistant=hass, yaml=YAML, services={"notify": ["smtp"]})
    await ctx.test_initialize()
    ctx.snoozer.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_TAG_driveway"}))

    frigate = Notification(ctx, message="Car on the driveway", action_data={"data": {"entity_id": "camera.driveway"}})
    await frigate.initialize()
    await frigate.deliver()
    assert not _delivered(frigate)
    assert not _delivered(await _send(ctx, "Car on the driveway", camera_entity_id="camera.driveway"))
    assert _delivered(await _send(ctx, "Person on the porch", camera_entity_id="camera.porch"))
    assert _delivered(await _send(ctx, "No entity involved"))


async def test_tag_snooze_matches_friendly_name_and_scenario(hass: HomeAssistant) -> None:
    hass.states.async_set("camera.front", "idle", {"friendly_name": "Driveway Probe"})
    ctx = TestingContext(
        homeassistant=hass,
        yaml=YAML
        + """
  scenarios:
    driveway_probe: {}
""",
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    ctx.snoozer.register_snooze(
        CommandType.SNOOZE, QualifiedTargetType.TAG, "Driveway_Probe", RecipientType.EVERYONE, None, timedelta(hours=1)
    )

    by_scenario = Notification(ctx, message="Vehicle at the gate", action_data={"apply_scenarios": "driveway_probe"})
    await by_scenario.initialize()
    await by_scenario.deliver()
    assert not _delivered(by_scenario)
    assert not _delivered(await _send(ctx, "Vehicle at the gate", camera_entity_id="camera.front"))
    assert _delivered(await _send(ctx, "Something else"))


async def test_tag_snooze_matches_the_sending_automation(hass: HomeAssistant) -> None:
    """The automation whose run carries the notification's context is a tag, by entity_id or name"""
    run = Context()
    other = Context()
    hass.states.async_set("automation.thermostat_offline", "on", {"friendly_name": "Thermostat Offline"}, context=run)
    hass.states.async_set("automation.garage_closed", "on", {"friendly_name": "Garage Closed"}, context=other)
    ctx = TestingContext(homeassistant=hass, yaml=YAML, services={"notify": ["smtp"]})
    await ctx.test_initialize()
    ctx.snoozer.register_snooze(
        CommandType.SNOOZE, QualifiedTargetType.TAG, "automation.thermostat_offline", RecipientType.EVERYONE, None, None
    )

    offline = Notification(ctx, message="Bathroom thermostat offline", ha_context=run)
    await offline.initialize()
    await offline.deliver()
    assert not _delivered(offline)
    assert offline.senders() == ["automation.thermostat_offline"]

    garage = Notification(ctx, message="Garage closed", ha_context=other)
    await garage.initialize()
    await garage.deliver()
    assert _delivered(garage)
    assert _delivered(await _send(ctx, "Sent by hand, no context"))


async def test_tag_snooze_matches_a_script_started_by_an_automation(hass: HomeAssistant) -> None:
    """A script's run has the automation's context as parent: both are senders, by name too"""
    automation_run = Context()
    script_run = Context(parent_id=automation_run.id)
    hass.states.async_set("automation.hourly", "on", {"friendly_name": "Hourly"}, context=automation_run)
    hass.states.async_set("script.chime", "on", {"friendly_name": "Hour Chime"}, context=script_run)
    ctx = TestingContext(homeassistant=hass, yaml=YAML, services={"notify": ["smtp"]})
    await ctx.test_initialize()
    ctx.snoozer.register_snooze(CommandType.SNOOZE, QualifiedTargetType.TAG, "hour chime", RecipientType.EVERYONE, None, None)

    uut = Notification(ctx, message="Ten o'clock", ha_context=script_run)
    await uut.initialize()
    await uut.deliver()
    assert not _delivered(uut)
    assert sorted(uut.senders()) == ["automation.hourly", "script.chime"]


async def test_user_tag_snooze_only_silences_that_user(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
  name: Supernotify
  platform: supernotify
  recipients:
    - person: person.bob_mctest
      email: bob@mctest.com
    - person: person.jane_macunit
      email: jane@macunit.org
  delivery:
    email:
      transport: email
      action: notify.smtp
""",
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    ctx.snoozer.register_snooze(
        CommandType.SNOOZE, QualifiedTargetType.TAG, "driveway camera", RecipientType.USER, "person.bob_mctest", None
    )

    uut = Notification(ctx, message="Car on the driveway", action_data={"data": {"entity_id": ["camera.driveway"]}})
    await uut.initialize()
    await uut.deliver()
    assert uut.deliveries["email"][EnvelopeOutcome.SUCCESS][0].target.email == ["jane@macunit.org"]  # type: ignore


async def test_user_snooze_everything_only_silences_that_user(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
  name: Supernotify
  platform: supernotify
  recipients:
    - person: person.bob_mctest
      email: bob@mctest.com
    - person: person.jane_macunit
      email: jane@macunit.org
  delivery:
    email:
      transport: email
      action: notify.smtp
""",
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    ctx.snoozer.register_snooze(
        CommandType.SNOOZE,
        target_type=GlobalTargetType.EVERYTHING,
        target=None,
        recipient_type=RecipientType.USER,
        recipient="person.bob_mctest",
        snooze_for=timedelta(hours=1),
    )

    uut = await _send(ctx, "Hello everyone")
    assert _delivered(uut)
    assert uut.deliveries["email"][EnvelopeOutcome.SUCCESS][0].target.email == ["jane@macunit.org"]  # type: ignore


def test_snooze_target_with_underscores() -> None:
    uut = Snoozer()
    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_camera.front_door"}))
    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_plain_email"}))

    assert sorted((s.target_type, s.target) for s in uut.snoozes.values()) == [
        (QualifiedTargetType.CAMERA, "camera.front_door"),
        (QualifiedTargetType.DELIVERY, "plain_email"),
    ]


def test_snooze_minutes_from_text_input_reply() -> None:
    uut = Snoozer()
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_camera.yard", "reply_text": "15"})
    )

    snooze = next(iter(uut.snoozes.values()))
    assert snooze.snooze_until is not None
    assert snooze.snooze_until - snooze.snoozed_at == timedelta(minutes=15)
