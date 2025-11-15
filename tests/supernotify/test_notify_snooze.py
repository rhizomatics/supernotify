from datetime import timedelta

from homeassistant.const import CONF_EMAIL
from homeassistant.core import Context, Event, HomeAssistant

from custom_components.supernotify import (
    ATTR_ACTION,
    ATTR_USER_ID,
    CONF_ACTION,
    CONF_PERSON,
    CONF_SELECTION,
    CONF_TRANSPORT,
    SELECTION_BY_SCENARIO,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_EMAIL,
    TRANSPORT_GENERIC,
    TRANSPORT_PERSISTENT,
    TRANSPORT_SMS,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import GlobalTargetType, QualifiedTargetType, RecipientType
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import SupernotifyAction
from custom_components.supernotify.snoozer import Snooze
from tests.supernotify.hass_setup_lib import register_mobile_app

DELIVERY: dict[str, dict] = {
    "email": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_TRANSPORT: TRANSPORT_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_media_player": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_TRANSPORT: TRANSPORT_PERSISTENT, CONF_SELECTION: [SELECTION_BY_SCENARIO]},
    "dummy": {CONF_TRANSPORT: "dummy"},
}


def test_snooze_delivery(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass)

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE,
               "foo", snooze_for=timedelta(hours=1))
    ]
    assert all(s["target"] == "foo" for s in uut.enquire_snoozes())
    assert all(
        s.snooze_until is not None and s.snooze_until -
        s.snoozed_at == timedelta(hours=1)
        for s in uut.context.snoozer.snoozes.values()
    )

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SILENCE_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == [Snooze(
        QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "foo")]
    assert all(
        s.snooze_until is None for s in uut.context.snoozer.snoozes.values())

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_foo_33"}))
    assert list(uut.context.snoozer.snoozes.values()) == [Snooze(
        QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "foo")]
    assert all(s.snooze_until is not None and s.snooze_until - s.snoozed_at == timedelta(minutes=33)
               for s in uut.context.snoozer.snoozes.values())

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_NORMAL_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == []


def test_snooze_everything(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass)
    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING,
               recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until -
        s.snoozed_at == timedelta(hours=1)
        for s in uut.context.snoozer.snoozes.values()
    )

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_NORMAL_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == []

    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING_99"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING,
               recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until -
        s.snoozed_at == timedelta(minutes=99)
        for s in uut.context.snoozer.snoozes.values()
    )


async def test_snooze_everything_for_person(hass: HomeAssistant) -> None:
    uut = SupernotifyAction(
        hass,
        recipients=[
            {CONF_PERSON: "person.bob_mctest",
                CONF_EMAIL: "bob@mctest.com", ATTR_USER_ID: "eee999111"},
            {CONF_PERSON: "person.jane_macunit",
                CONF_EMAIL: "jane@macunit.org", ATTR_USER_ID: "fff444222"},
        ],
        deliveries=DELIVERY,
    )
    await uut.initialize()
    register_mobile_app(uut.context.people_registry,
                        person="person.bob_mctest")
    plain_notify = Notification(uut.context, "hello")
    delivery = Delivery(
        "email", DELIVERY["email"], uut.context.delivery_registry.transports["email"])
    await plain_notify.initialize()
    assert plain_notify.generate_recipients(delivery)[0].email == [
        "bob@mctest.com",
        "jane@macunit.org",
    ]

    uut.on_mobile_action(
        Event("mobile_action", data={
              ATTR_ACTION: "SUPERNOTIFY_SNOOZE_USER_EVERYTHING"}, context=Context(user_id="eee999111"))
    )
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING,
               recipient_type=RecipientType.USER, recipient="person.bob_mctest")
    ]
    await plain_notify.initialize()
    assert plain_notify.generate_recipients(delivery)[0].email == [
        "jane@macunit.org"]

    uut.on_mobile_action(
        Event("mobile_action", data={
              ATTR_ACTION: "SUPERNOTIFY_NORMAL_USER_EVERYTHING"}, context=Context(user_id="eee999111"))
    )
    assert list(uut.context.snoozer.snoozes.values()) == []
    await plain_notify.initialize()
    assert plain_notify.generate_recipients(delivery)[0].email == [
        "bob@mctest.com",
        "jane@macunit.org",
    ]

    uut.shutdown()


def test_clear_snoozes(mock_hass: HomeAssistant) -> None:
    uut = SupernotifyAction(mock_hass)
    uut.on_mobile_action(Event("mobile_action", data={
                         ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING,
               recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until -
        s.snoozed_at == timedelta(hours=1)
        for s in uut.context.snoozer.snoozes.values()
    )
    uut.clear_snoozes()
    assert list(uut.context.snoozer.snoozes.values()) == []
