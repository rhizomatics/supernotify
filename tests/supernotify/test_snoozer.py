from homeassistant.core import Event

from custom_components.supernotify import (
    ATTR_ACTION,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType, Target
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.snoozer import Snooze, Snoozer


def test_do_nothing_filter_recipients() -> None:
    uut = Snoozer()
    filtered = uut.filter_recipients(
        Target(["notify.abc", "joe@mctest.com", "person.joe"]), PRIORITY_MEDIUM, "email", {}, ["email"], {}
    )
    assert filtered == Target(["notify.abc", "joe@mctest.com", "person.joe"])


def test_filter_mobile_device_action(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    pre_call_person = mock_people_registry.people["person.bidey_in"]
    uut: Snoozer = Snoozer()
    uut.register_snooze(
        CommandType.SNOOZE,
        target_type=QualifiedTargetType.ACTION,
        target="mobile_app_nophone",
        recipient_type=RecipientType.USER,
        recipient="person.bidey_in",
        snooze_for=24 * 60 * 60,
        reason="Action Failure",
    )
    recipients: Target = uut.filter_recipients(
        Target({"action": ["mobile_app_nophone", "mobile_app.ipad"], "person_id": ["person.bidey_in", "person.test_otest"]}),
        PRIORITY_MEDIUM,
        "email",
        {},
        ["email"],
        {},
    )
    assert recipients.actions == ["mobile_app.ipad"]  # mobile suppressed
    assert recipients.person_ids == ["person.bidey_in", "person.test_otest"]  # person untouched

    # check that the original recipients haven't been messed with
    assert mock_people_registry.people["person.bidey_in"] == pre_call_person


def test_check_notification_for_snooze_global() -> None:
    uut: Snoozer = Snoozer()
    assert uut.current_snoozes() == []
    assert not uut.is_global_snooze()

    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert uut.is_global_snooze()
    assert uut.current_snoozes() == [(Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE))]

    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_NONCRITICAL"}))
    assert not uut.is_global_snooze(PRIORITY_CRITICAL)
    assert uut.current_snoozes(PRIORITY_CRITICAL) == []
    assert uut.is_global_snooze()
    assert uut.current_snoozes() == [Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)]


def test_check_notification_for_snooze_qualified(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut: Snoozer = Snoozer()
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_chime"}), mock_people_registry.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SILENCE_EVERYONE_CAMERA_Yard"}), mock_people_registry.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_TRANSPORT_email"}), mock_people_registry.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_TRANSPORT_LASER"}), mock_people_registry.people
    )
    assert uut.current_snoozes(delivery_names=["chime", "plain_email"], delivery_definitions=mock_context.deliveries) == [
        Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "chime"),
        Snooze(QualifiedTargetType.CAMERA, RecipientType.EVERYONE, "Yard"),
        Snooze(QualifiedTargetType.TRANSPORT, RecipientType.EVERYONE, "email"),
    ]
