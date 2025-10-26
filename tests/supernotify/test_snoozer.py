from homeassistant.core import Event

from custom_components.supernotify import (
    ATTR_ACTION,
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
    CommandType,
    GlobalTargetType,
    QualifiedTargetType,
    RecipientType,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.snoozer import Snooze, Snoozer


def test_do_nothing_filter_recipients() -> None:
    uut = Snoozer()
    assert uut.filter_recipients([{CONF_PERSON: "test_1"}], PRIORITY_MEDIUM, "email", {}, ["email"], {}) == [
        {CONF_PERSON: "test_1"}
    ]


def test_filter_mobile_device_action(mock_context: Context) -> None:
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
    recipients = uut.filter_recipients(list(mock_context.people.values()), PRIORITY_MEDIUM, "email", {}, ["email"], {})
    assert recipients == [
        {CONF_PERSON: "person.new_home_owner"},
        {CONF_PERSON: "person.bidey_in", CONF_MOBILE_DEVICES: [{CONF_NOTIFY_ACTION: "mobile_app_iphone"}]},
    ]
    # check that the original recipients haven't been messed with
    assert mock_context.people["person.bidey_in"] == {
        CONF_PERSON: "person.bidey_in",
        CONF_MOBILE_DEVICES: [{CONF_NOTIFY_ACTION: "mobile_app_iphone"}, {CONF_NOTIFY_ACTION: "mobile_app_nophone"}],
    }


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


def test_check_notification_for_snooze_qualified(mock_context: Context) -> None:
    uut: Snoozer = Snoozer()
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_chime"}), mock_context.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SILENCE_EVERYONE_CAMERA_Yard"}), mock_context.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_METHOD_email"}), mock_context.people
    )
    uut.handle_command_event(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_METHOD_LASER"}), mock_context.people
    )
    assert uut.current_snoozes(delivery_names=["chime", "gmail"], delivery_definitions=mock_context.deliveries) == [
        Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "chime"),
        Snooze(QualifiedTargetType.CAMERA, RecipientType.EVERYONE, "Yard"),
        Snooze(QualifiedTargetType.METHOD, RecipientType.EVERYONE, "email"),
    ]
