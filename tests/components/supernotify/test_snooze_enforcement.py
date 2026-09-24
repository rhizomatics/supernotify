from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Event

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
