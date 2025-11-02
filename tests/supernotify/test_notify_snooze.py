from homeassistant.core import Context, Event, HomeAssistant

from custom_components.supernotify import (
    ATTR_ACTION,
    ATTR_USER_ID,
    CONF_ACTION,
    CONF_METHOD,
    CONF_PERSON,
    CONF_SELECTION,
    METHOD_ALEXA_MEDIA_PLAYER,
    METHOD_CHIME,
    METHOD_EMAIL,
    METHOD_GENERIC,
    METHOD_PERSISTENT,
    METHOD_SMS,
    SELECTION_BY_SCENARIO,
    GlobalTargetType,
    QualifiedTargetType,
    RecipientType,
)
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.notify import SuperNotificationAction
from custom_components.supernotify.snoozer import Snooze
from tests.supernotify.hass_setup_lib import register_mobile_app

DELIVERY: dict[str, dict] = {
    "email": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp"},
    "text": {CONF_METHOD: METHOD_SMS, CONF_ACTION: "notify.sms"},
    "chime": {CONF_METHOD: METHOD_CHIME, "entities": ["switch.bell_1", "script.siren_2"]},
    "alexa_media_player": {CONF_METHOD: METHOD_ALEXA_MEDIA_PLAYER, CONF_ACTION: "notify.alexa_media_player"},
    "chat": {CONF_METHOD: METHOD_GENERIC, CONF_ACTION: "notify.my_chat_server"},
    "persistent": {CONF_METHOD: METHOD_PERSISTENT, CONF_SELECTION: [SELECTION_BY_SCENARIO]},
    "dummy": {CONF_METHOD: "dummy"},
}


def test_snooze_delivery(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(mock_hass)

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "foo", snooze_for=3600)
    ]
    assert all(s["target"] == "foo" for s in uut.enquire_snoozes())
    assert all(
        s.snooze_until is not None and s.snooze_until - s.snoozed_at == 3600 for s in uut.context.snoozer.snoozes.values()
    )

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SILENCE_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == [Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "foo")]
    assert all(s.snooze_until is None for s in uut.context.snoozer.snoozes.values())

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_DELIVERY_foo_33"}))
    assert list(uut.context.snoozer.snoozes.values()) == [Snooze(QualifiedTargetType.DELIVERY, RecipientType.EVERYONE, "foo")]
    assert all(s.snooze_until is not None and s.snooze_until - s.snoozed_at == 33 for s in uut.context.snoozer.snoozes.values())

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_NORMAL_EVERYONE_DELIVERY_foo"}))
    assert list(uut.context.snoozer.snoozes.values()) == []


def test_snooze_everything(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(mock_hass)
    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING, recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until - s.snoozed_at == 3600
        for s in uut.context.snoozer.snoozes.values()
    )

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_NORMAL_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == []

    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING_99"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING, recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until - s.snoozed_at == 99
        for s in uut.context.snoozer.snoozes.values()
    )


async def test_snooze_everything_for_person(hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(
        hass,
        recipients=[
            {CONF_PERSON: "person.bob_mctest", ATTR_USER_ID: "eee999111"},
            {CONF_PERSON: "person.jane_macunit", ATTR_USER_ID: "fff444222"},
        ],
        deliveries=DELIVERY,
    )
    await uut.initialize()
    register_mobile_app(uut.context, person="person.bob_mctest")
    plain_notify = Notification(uut.context, "hello")
    await plain_notify.initialize()
    assert [p[CONF_PERSON] for p in plain_notify.generate_recipients("email", uut.context.delivery_method("email"))] == [
        "person.bob_mctest",
        "person.jane_macunit",
    ]

    uut.on_mobile_action(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_USER_EVERYTHING"}, context=Context(user_id="eee999111"))
    )
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING, recipient_type=RecipientType.USER, recipient="person.bob_mctest")
    ]
    await plain_notify.initialize()
    assert [p[CONF_PERSON] for p in plain_notify.generate_recipients("email", uut.context.delivery_method("email"))] == [
        "person.jane_macunit"
    ]

    uut.on_mobile_action(
        Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_NORMAL_USER_EVERYTHING"}, context=Context(user_id="eee999111"))
    )
    assert list(uut.context.snoozer.snoozes.values()) == []
    await plain_notify.initialize()
    assert [p[CONF_PERSON] for p in plain_notify.generate_recipients("email", uut.context.delivery_method("email"))] == [
        "person.bob_mctest",
        "person.jane_macunit",
    ]

    uut.shutdown()


def test_clear_snoozes(mock_hass: HomeAssistant) -> None:
    uut = SuperNotificationAction(mock_hass)
    uut.on_mobile_action(Event("mobile_action", data={ATTR_ACTION: "SUPERNOTIFY_SNOOZE_EVERYONE_EVERYTHING"}))
    assert list(uut.context.snoozer.snoozes.values()) == [
        Snooze(GlobalTargetType.EVERYTHING, recipient_type=RecipientType.EVERYONE)
    ]
    assert all(
        s.target is None and s.snooze_until is not None and s.snooze_until - s.snoozed_at == 3600
        for s in uut.context.snoozer.snoozes.values()
    )
    uut.clear_snoozes()
    assert list(uut.context.snoozer.snoozes.values()) == []
