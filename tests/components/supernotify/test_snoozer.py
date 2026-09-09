from __future__ import annotations

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
from custom_components.supernotify.snoozer import STORAGE_KEY, STORAGE_VERSION, Snooze, Snoozer
from custom_components.supernotify.transports.email import EmailTransport

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.context import Context
    from custom_components.supernotify.hass_api import HomeAssistantAPI
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
        "BADCMD",  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
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
    snooze.target_type = "UNKNOWN_TYPE"  # type: ignore[assignment]  # ty: ignore[invalid-assignment]
    uut.snoozes["test"] = snooze
    assert uut.current_snoozes(PRIORITY_MEDIUM, delivery) == []


def test_snooze_to_storage_dict_round_trip_global() -> None:
    snooze = Snooze(GlobalTargetType.NONCRITICAL, RecipientType.EVERYONE, snooze_for=timedelta(minutes=30), reason="quiet time")
    restored = Snooze.from_storage_dict(snooze.to_storage_dict())
    assert restored is not None
    assert restored == snooze  # short_key() equality
    assert restored.target_type == GlobalTargetType.NONCRITICAL
    assert isinstance(restored.target_type, GlobalTargetType)
    assert restored.recipient_type == RecipientType.EVERYONE
    assert restored.reason == "quiet time"
    assert restored.snoozed_at == snooze.snoozed_at
    assert restored.snooze_until == snooze.snooze_until


def test_snooze_to_storage_dict_round_trip_qualified_with_recipient() -> None:
    snooze = Snooze(
        QualifiedTargetType.CAMERA,
        RecipientType.USER,
        target="Yard",
        recipient="person.bidey_in",
        reason="User command",
    )
    restored = Snooze.from_storage_dict(snooze.to_storage_dict())
    assert restored is not None
    assert restored == snooze
    assert isinstance(restored.target_type, QualifiedTargetType)
    assert restored.target_type == QualifiedTargetType.CAMERA
    assert restored.target == "Yard"
    assert restored.recipient == "person.bidey_in"
    assert restored.recipient_type == RecipientType.USER
    # a snooze without snooze_for never expires
    assert restored.snooze_until is None
    assert restored.active()


def test_snooze_from_storage_dict_malformed_returns_none() -> None:
    assert Snooze.from_storage_dict({}) is None
    assert Snooze.from_storage_dict({"target_type_class": "GlobalTargetType", "target_type": "NOT_A_REAL_VALUE"}) is None


def test_snoozer_persist_is_noop_without_hass_api() -> None:
    """Snoozer() constructed bare (as every pre-existing test in this module does) must not
    attempt to persist - hass_api is None until initialize() is called."""
    uut = Snoozer()
    assert uut.hass_api is None
    uut.register_snooze(
        CommandType.SNOOZE, GlobalTargetType.EVERYTHING, None, RecipientType.EVERYONE, None, timedelta(minutes=5)
    )
    assert len(uut.snoozes) == 1  # no exception raised trying to persist


async def test_snoozer_initialize_with_no_prior_storage(unmocked_hass_api: HomeAssistantAPI, hass_storage: dict) -> None:
    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)
    assert uut.hass_api is unmocked_hass_api
    assert uut.snoozes == {}
    assert STORAGE_KEY not in hass_storage


async def test_snoozer_initialize_restores_active_and_skips_expired_snoozes(
    unmocked_hass_api: HomeAssistantAPI, hass_storage: dict
) -> None:
    active = Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE, snooze_for=timedelta(hours=1))
    expired = Snooze(QualifiedTargetType.CAMERA, RecipientType.EVERYONE, target="Yard", snooze_for=timedelta(seconds=-1))
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": [active.to_storage_dict(), expired.to_storage_dict()],
    }

    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)

    assert list(uut.snoozes.values()) == [active]


async def test_snoozer_initialize_discards_malformed_entries(unmocked_hass_api: HomeAssistantAPI, hass_storage: dict) -> None:
    good = Snooze(GlobalTargetType.EVERYTHING, RecipientType.EVERYONE)
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": [good.to_storage_dict(), {"garbage": True}],
    }

    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)

    assert list(uut.snoozes.values()) == [good]


async def test_snoozer_register_snooze_persists_and_survives_reload(
    hass: HomeAssistant, unmocked_hass_api: HomeAssistantAPI, hass_storage: dict
) -> None:
    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)
    uut.register_snooze(
        CommandType.SNOOZE,
        QualifiedTargetType.DELIVERY,
        "email",
        RecipientType.EVERYONE,
        None,
        timedelta(hours=1),
        reason="test persistence",
    )
    await hass.async_block_till_done()  # let the fire-and-forget Store.async_save complete

    assert STORAGE_KEY in hass_storage
    assert len(hass_storage[STORAGE_KEY]["data"]) == 1

    # simulate a Home Assistant restart: a fresh Snoozer restores from the same storage
    reloaded = Snoozer()
    await reloaded.initialize(unmocked_hass_api)
    assert len(reloaded.snoozes) == 1
    restored_snooze = next(iter(reloaded.snoozes.values()))
    assert restored_snooze.target_type == QualifiedTargetType.DELIVERY
    assert restored_snooze.target == "email"
    assert restored_snooze.reason == "test persistence"


async def test_snoozer_clear_persists_empty_state(
    hass: HomeAssistant, unmocked_hass_api: HomeAssistantAPI, hass_storage: dict
) -> None:
    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)
    uut.register_snooze(CommandType.SNOOZE, GlobalTargetType.EVERYTHING, None, RecipientType.EVERYONE, None, None)
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"]

    assert uut.clear() == 1
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"] == []


async def test_snoozer_purge_snoozes_persists_after_removal(
    hass: HomeAssistant, unmocked_hass_api: HomeAssistantAPI, hass_storage: dict
) -> None:
    uut = Snoozer()
    await uut.initialize(unmocked_hass_api)
    uut.register_snooze(
        CommandType.SNOOZE, GlobalTargetType.EVERYTHING, None, RecipientType.EVERYONE, None, timedelta(seconds=-1)
    )
    await hass.async_block_till_done()
    assert len(hass_storage[STORAGE_KEY]["data"]) == 1

    uut.purge_snoozes()
    await hass.async_block_till_done()
    assert hass_storage[STORAGE_KEY]["data"] == []
