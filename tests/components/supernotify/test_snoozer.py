from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Event

from custom_components.supernotify.const import (
    ATTR_ACTION,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType, Target
from custom_components.supernotify.snoozer import Snooze, Snoozer
from custom_components.supernotify.transports.email import EmailTransport

if TYPE_CHECKING:
    from custom_components.supernotify.context import Context
    from custom_components.supernotify.people import PeopleRegistry


def test_do_nothing_filter_recipients(mock_context) -> None:
    uut = Snoozer()
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    filtered = uut.filter_recipients(Target(["notify.abc", "joe@mctest.com", "person.joe"]), PRIORITY_MEDIUM, delivery)
    assert filtered == Target(["notify.abc", "joe@mctest.com", "person.joe"])


def test_filter_mobile_device_action(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    pre_call_person = mock_people_registry.people["person.bidey_in"]
    uut: Snoozer = Snoozer()
    uut.register_snooze(
        CommandType.SNOOZE,
        target_type=QualifiedTargetType.MOBILE,
        target="mobile_app_nophone",
        recipient_type=RecipientType.USER,
        recipient="person.bidey_in",
        snooze_for=timedelta(days=1),
        reason="Action Failure",
    )
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    recipients: Target = uut.filter_recipients(
        Target({
            "mobile_app_id": ["mobile_app_nophone", "mobile_app_ipad"],
            "person_id": ["person.bidey_in", "person.test_otest"],
        }),
        PRIORITY_MEDIUM,
        delivery,
    )
    assert recipients.mobile_app_ids == ["mobile_app_ipad"]  # mobile suppressed
    assert recipients.person_ids == ["person.bidey_in", "person.test_otest"]  # person untouched

    # check that the original recipients haven't been messed with
    assert mock_people_registry.people["person.bidey_in"] == pre_call_person


def test_check_notification_for_snooze_global(mock_context: Context) -> None:
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    uut: Snoozer = Snoozer()
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == []
    assert not uut.is_global_snooze()

    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert uut.is_global_snooze()
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == [(Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE))]

    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_NONCRITICAL"}))
    assert not uut.is_global_snooze(PRIORITY_CRITICAL)
    assert uut.current_snoozes(PRIORITY_CRITICAL, delivery) == []
    assert uut.is_global_snooze()
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == [Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)]


def test_check_notification_for_snooze_qualified(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    uut: Snoozer = Snoozer()
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_chime"}),
        mock_people_registry.enabled_recipients(),
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SILENCE_EVERYONE_CAMERA_Yard"}),
        mock_people_registry.enabled_recipients(),
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_TRANSPORT_email"}),
        mock_people_registry.enabled_recipients(),
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_TRANSPORT_LASER"}),
        mock_people_registry.enabled_recipients(),
    )
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == [
        Snooze(QualifiedTargetType.CAMERA, RecipientType.EVERYONE, "Yard"),
        Snooze(QualifiedTargetType.TRANSPORT, RecipientType.EVERYONE, "email"),
    ]


def test_snooze_not_equal_to_non_snooze() -> None:
    s = Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)
    assert s != "not a snooze"
    assert s != 42


def test_snooze_repr() -> None:
    s = Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)
    assert "GLOBAL" in repr(s)


def test_handle_command_event_no_action() -> None:
    uut = Snoozer()
    uut.handle_command_event(Event("mobile_action", data={}))
    assert uut.snoozes == {}


def test_handle_command_event_short_name() -> None:
    uut = Snoozer()
    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE"}))
    assert uut.snoozes == {}


def test_handle_command_event_bad_enum() -> None:
    uut = Snoozer()
    uut.handle_command_event(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_INVALIDCMD_EVERYONE_EVERYTHING"}))
    assert uut.snoozes == {}


def test_purge_expired_snoozes() -> None:
    uut = Snoozer()
    uut.register_snooze(
        CommandType.SNOOZE,
        target_type=GlobalTargetType.EVERYTHING,
        target=None,
        recipient_type=RecipientType.EVERYONE,
        recipient=None,
        snooze_for=timedelta(seconds=-1),
    )
    assert len(uut.snoozes) == 1
    uut.purge_snoozes()
    assert uut.snoozes == {}


def test_register_snooze_unknown_cmd() -> None:
    uut = Snoozer()
    uut.register_snooze(
        "BADCMD",  # type: ignore[arg-type]
        GlobalTargetType.EVERYTHING,
        None,
        RecipientType.EVERYONE,
        None,
        None,
    )
    assert uut.snoozes == {}


def test_current_snoozes_delivery_and_priority(mock_context) -> None:
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    uut = Snoozer()
    uut.register_snooze(CommandType.SNOOZE, QualifiedTargetType.DELIVERY, "email", RecipientType.EVERYONE, None, None)
    uut.register_snooze(CommandType.SNOOZE, QualifiedTargetType.PRIORITY, PRIORITY_MEDIUM, RecipientType.EVERYONE, None, None)
    snoozes = uut.current_snoozes(PRIORITY_MEDIUM, delivery)
    assert len(snoozes) == 2


def test_current_snoozes_unhandled_target_type(mock_context) -> None:
    delivery = Delivery("email", {}, EmailTransport(mock_context))
    uut = Snoozer()
    snooze = Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)
    snooze.target_type = "UNKNOWN_TYPE"  # type: ignore[assignment]
    uut.snoozes["test"] = snooze
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == []
