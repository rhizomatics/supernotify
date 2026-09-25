"""Sentences for Home Assistant's built-in conversation agent (sentences.py)

The agent itself needs hassil and the rest of the voice stack, so it isn't run here - the
commands are called directly, and the trigger registration is checked with it patched.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import CONF_LLM_TOOLS, CONF_SENTENCE_COMMANDS
from custom_components.supernotify.model import GlobalTargetType, RecipientType
from custom_components.supernotify.sentences import RESPONSES, SENTENCES, async_respond

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from custom_components.supernotify.engine import SupernotifyEngine

JEY_USER_ID = "jey-user-id"


async def _setup(
    hass: HomeAssistant, sentence_commands: bool = False, extra_people: dict[str, str] | None = None
) -> tuple[SupernotifyEngine, list[ServiceCall]]:
    calls: list[ServiceCall] = []

    async def _mock_notification(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("testing", "mock_notification", _mock_notification)
    hass.states.async_set("person.jey_burrows", "home", {"friendly_name": "Jey Burrows", "user_id": JEY_USER_ID})
    hass.states.async_set("person.bob", "home", {"friendly_name": "Bob"})
    for entity_id, friendly_name in (extra_people or {}).items():
        hass.states.async_set(entity_id, "home", {"friendly_name": friendly_name})
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "delivery": {
                    "chat": {
                        "transport": "generic",
                        "action": "testing.mock_notification",
                        "target_required": "never",
                        "inclusion": ["default"],
                    }
                },
                "recipients": [
                    {"person": "person.jey_burrows"},
                    {"person": "person.bob"},
                    *({"person": entity_id} for entity_id in extra_people or {}),
                ],
            }
        },
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    if sentence_commands:
        hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_LLM_TOOLS: {CONF_SENTENCE_COMMANDS: True}})
        await hass.async_block_till_done()
    return entry.runtime_data, calls


async def test_notify_named_recipient(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "jey burrows", "message": "dinner is ready"}, Context())

    assert response == "Sent to jey burrows"
    assert [c.data["message"] for c in calls] == ["dinner is ready"]
    assert engine.last_notification is not None
    assert engine.last_notification._target is not None
    assert engine.last_notification._target.person_ids == ["person.jey_burrows"]


async def test_notify_by_unique_first_name(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "jey", "message": "dinner needs to be made"}, Context())

    assert response == "Sent to jey"
    assert len(calls) == 1
    assert engine.last_notification is not None
    assert engine.last_notification._target is not None
    assert engine.last_notification._target.person_ids == ["person.jey_burrows"]


async def test_notify_asks_which_when_first_name_shared(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, extra_people={"person.jey_smith": "Jey Smith"})

    response = await async_respond(engine, "notify", {"name": "Jey", "message": "hello"}, Context())

    assert response == "Which Jey do you mean: Jey Burrows or Jey Smith?"
    assert calls == []


async def test_full_name_wins_over_shared_first_name(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, extra_people={"person.jey_smith": "Jey Smith"})

    assert await async_respond(engine, "notify", {"name": "jey smith", "message": "hi"}, Context()) == "Sent to jey smith"
    assert len(calls) == 1


async def test_notify_everyone(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "everyone", "message": "leaving now"}, Context())

    assert response == "Sent"
    assert len(calls) == 1
    assert engine.last_notification is not None
    assert engine.last_notification._target is None


async def test_notify_unknown_recipient_lists_known(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "mallory", "message": "hi"}, Context())

    assert response == "I don't know anyone called mallory. I can notify Bob, Jey Burrows, or everyone"
    assert calls == []


async def test_snooze_minutes_for_person_asking(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_minutes", {"minutes": "30"}, Context(user_id=JEY_USER_ID))

    assert response.startswith("Snoozed your notifications until ")
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.target_type == GlobalTargetType.EVERYTHING
    assert snooze.recipient_type == RecipientType.USER
    assert snooze.recipient == "person.jey_burrows"
    assert snooze.snooze_until is not None


async def test_snooze_for_the_next_minutes(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_minutes", {"minutes": "the next 40"}, Context())

    assert response.startswith("Snoozed all notifications until ")
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.snooze_until is not None


async def test_snooze_minutes_must_be_a_number(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_minutes", {"minutes": "ten"}, Context())

    assert "as a number" in response
    assert engine.context.snoozer.snoozes == {}


@pytest.mark.parametrize(
    ("asked_at", "spoken", "expected", "said_back"),
    [
        ("10:00", "15:30", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "3:30 pm", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "3pm", "2026-09-24 15:00", "3:00pm"),
        ("10:00", "12 a.m.", "2026-09-25 00:00", "12:00am"),
        ("10:00", "09:15", "2026-09-25 09:15", "9:15am"),
        ("10:00", "15.30", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "1530", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "3", "2026-09-24 15:00", "3:00pm"),
        ("10:00", "9", "2026-09-24 21:00", "9:00pm"),
        ("10:00", "11", "2026-09-24 11:00", "11:00am"),
        ("10:00", "12", "2026-09-24 12:00", "12:00pm"),
        ("10:00", "18", "2026-09-24 18:00", "6:00pm"),
        ("10:00", "0", "2026-09-25 00:00", "12:00am"),
        ("10:00", "midnight", "2026-09-25 00:00", "12:00am"),
        ("10:00", "Noon", "2026-09-24 12:00", "12:00pm"),
        ("10:00", "3:30", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "330", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "03:30", "2026-09-25 03:30", "3:30am"),
        ("10:00", "half past three", "2026-09-24 15:30", "3:30pm"),
        ("10:00", "Half past 11", "2026-09-24 11:30", "11:30am"),
        ("02:30", "3:30", "2026-09-24 03:30", "3:30am"),
        ("02:30", "half past three", "2026-09-24 03:30", "3:30am"),
        ("14:30", "3:30", "2026-09-24 15:30", "3:30pm"),
        ("14:30", "03:30", "2026-09-25 03:30", "3:30am"),
        ("23:00", "3", "2026-09-25 03:00", "3:00am"),
    ],
)
async def test_snooze_until_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, asked_at: str, spoken: str, expected: str, said_back: str
) -> None:
    hour, minute = (int(part) for part in asked_at.split(":"))
    freezer.move_to(dt_util.as_utc(dt.datetime(2026, 9, 24, hour, minute, tzinfo=dt_util.get_default_time_zone())))
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_until", {"time": spoken}, Context())

    assert response == f"Snoozed all notifications until {said_back}"
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.snooze_until is not None
    assert dt_util.as_local(snooze.snooze_until).strftime("%Y-%m-%d %H:%M") == expected


@pytest.mark.parametrize("spoken", ["30", "25:00", "2500", "13pm", "teatime", "half three", "half past thirteen", "past three"])
async def test_snooze_until_must_be_a_time(hass: HomeAssistant, spoken: str) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_until", {"time": spoken}, Context())

    assert "Say a time like 15:30" in response
    assert engine.context.snoozer.snoozes == {}


async def test_mute_until_i_say_silences(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_until", {"time": "I say"}, Context())

    assert response == "Silenced all notifications until you turn them back on"
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.snooze_until is None


async def test_snooze_hour_for_everyone_when_asker_unknown(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_hour", {}, Context())

    assert response.startswith("Snoozed all notifications until ")
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.recipient_type == RecipientType.EVERYONE


async def test_silence_then_resume(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)
    asker = Context(user_id=JEY_USER_ID)

    assert await async_respond(engine, "silence", {}, asker) == "Silenced your notifications until you turn them back on"
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.snooze_until is None

    assert await async_respond(engine, "resume", {}, asker) == "Turned your notifications back on"
    assert engine.context.snoozer.snoozes == {}


async def test_silence_everyone_stops_notifications(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    await async_respond(engine, "silence", {}, Context())
    response = await async_respond(engine, "notify", {"name": "everyone", "message": "hello"}, Context())

    assert response == "Sorry, the notification wasn't sent"
    assert calls == []


async def test_last_notification(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    assert await async_respond(engine, "last", {}, Context()) == (
        "There haven't been any notifications since Home Assistant started"
    )
    await engine.async_send_message("washing machine finished")

    response = await async_respond(engine, "last", {}, Context())

    assert response.endswith(": washing machine finished. Sent by chat")


async def test_unknown_command(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    assert "doesn't know" in await async_respond(engine, "dance", {}, Context())


async def test_sentences_not_registered_unless_switched_on(hass: HomeAssistant) -> None:
    with patch("custom_components.supernotify.sentences.async_initialize_triggers") as initialize:
        await _setup(hass)

    initialize.assert_not_called()


async def test_sentences_registered_and_answer(hass: HomeAssistant) -> None:
    remove = Mock()
    initialize = AsyncMock(return_value=remove)

    async def validate(_hass: HomeAssistant, config: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return config

    with (
        patch("custom_components.supernotify.sentences.async_validate_trigger_config", side_effect=validate),
        patch("custom_components.supernotify.sentences.async_initialize_triggers", initialize),
    ):
        _engine, calls = await _setup(hass, sentence_commands=True)

    configs: list[dict[str, Any]] = initialize.call_args.args[1]
    assert {c["id"]: c["command"] for c in configs} == {
        f"{language}.{command}": sentences
        for language, commands in SENTENCES.items()
        for command, sentences in commands.items()
    }
    assert all(c["platform"] == "conversation" for c in configs)

    action = initialize.call_args.args[2]
    result = await action({
        "trigger": {
            "id": "en.notify",
            "slots": {"name": "Bob", "message": "the post has come"},
            "user_input": {"context": {"id": "abc", "user_id": JEY_USER_ID}},
        }
    })
    assert result.conversation_response == "Sent to Bob"
    assert calls[0].context.user_id == JEY_USER_ID

    result = await action({
        "trigger": {
            "id": "it.notify",
            "slots": {"name": "Bob", "message": "è arrivata la posta"},
            "user_input": {"context": {"id": "def", "user_id": JEY_USER_ID}},
        }
    })
    assert result.conversation_response == "Inviata a Bob"
    assert calls[1].data["message"] == "è arrivata la posta"

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    remove.assert_called_once()


async def test_sentences_not_registered_when_conversation_unavailable(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.supernotify.sentences.async_validate_trigger_config",
            side_effect=ImportError("No module named 'hassil'"),
        ),
        patch("custom_components.supernotify.sentences.async_initialize_triggers") as initialize,
    ):
        engine, _calls = await _setup(hass, sentence_commands=True)

    initialize.assert_not_called()
    assert engine is not None


def test_every_language_has_every_command_and_response() -> None:
    for language, commands in SENTENCES.items():
        assert commands.keys() == SENTENCES["en"].keys(), language
        assert all(commands.values()), language
    assert RESPONSES.keys() == SENTENCES.keys()
    for language, responses in RESPONSES.items():
        assert responses.keys() == RESPONSES["en"].keys(), language


async def test_italian_notify_named_recipient(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "Jey Burrows", "message": "la cena è pronta"}, Context(), "it")

    assert response == "Inviata a Jey Burrows"
    assert [c.data["message"] for c in calls] == ["la cena è pronta"]
    assert engine.last_notification is not None
    assert engine.last_notification._target is not None
    assert engine.last_notification._target.person_ids == ["person.jey_burrows"]


async def test_italian_notify_everyone(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "tutti", "message": "esco adesso"}, Context(), "it")

    assert response == "Inviata"
    assert len(calls) == 1
    assert engine.last_notification is not None
    assert engine.last_notification._target is None


async def test_italian_notify_unknown_recipient_lists_known(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass)

    response = await async_respond(engine, "notify", {"name": "mallory", "message": "ciao"}, Context(), "it")

    assert response.startswith("Non conosco nessuno che si chiama mallory. Posso avvisare ")
    assert response.endswith(", oppure tutti")
    assert calls == []


async def test_italian_snooze_silence_resume(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)
    asker = Context(user_id=JEY_USER_ID)

    assert "con un numero" in await async_respond(engine, "snooze_minutes", {"minutes": "dieci"}, asker, "it")
    assert engine.context.snoozer.snoozes == {}

    response = await async_respond(engine, "snooze_minutes", {"minutes": "i prossimi 30"}, asker, "it")
    assert response.startswith("Ho posticipato le tue notifiche fino alle ")
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.recipient == "person.jey_burrows"

    assert await async_respond(engine, "resume", {}, asker, "it") == "Ho riattivato le tue notifiche"
    assert engine.context.snoozer.snoozes == {}

    response = await async_respond(engine, "snooze_hour", {}, Context(), "it")
    assert response.startswith("Ho posticipato tutte le notifiche fino alle ")
    assert await async_respond(engine, "silence", {}, Context(), "it") == (
        "Ho silenziato tutte le notifiche finché non le riattivi"
    )
    response = await async_respond(engine, "notify", {"name": "tutti", "message": "ciao"}, Context(), "it")
    assert response == "Mi dispiace, la notifica non è stata inviata"


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("15:30", "2026-09-24 15:30"),
        ("15.30", "2026-09-24 15:30"),
        ("15", "2026-09-24 15:00"),
        ("7", "2026-09-25 07:00"),
    ],
)
async def test_italian_snooze_until_24_hour_clock(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, spoken: str, expected: str
) -> None:
    freezer.move_to(dt_util.as_utc(dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt_util.get_default_time_zone())))
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_until", {"time": spoken}, Context(), "it")

    assert response == f"Ho posticipato tutte le notifiche fino alle {expected[-5:]}"
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.snooze_until is not None
    assert dt_util.as_local(snooze.snooze_until).strftime("%Y-%m-%d %H:%M") == expected


@pytest.mark.parametrize("spoken", ["25", "15:75", "pranzo"])
async def test_italian_snooze_until_must_be_a_time(hass: HomeAssistant, spoken: str) -> None:
    engine, _calls = await _setup(hass)

    response = await async_respond(engine, "snooze_until", {"time": spoken}, Context(), "it")

    assert response.startswith("Dimmi un orario come 15 o 15:30")
    assert engine.context.snoozer.snoozes == {}


async def test_italian_last_notification(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    assert await async_respond(engine, "last", {}, Context(), "it") == (
        "Non ci sono state notifiche da quando Home Assistant si è avviato"
    )
    await engine.async_send_message("lavatrice finita")

    response = await async_respond(engine, "last", {}, Context(), "it")

    assert response.startswith("Alle ")
    assert response.endswith(": lavatrice finita. Inviata da chat")


async def test_unknown_language_answers_in_english(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    assert await async_respond(engine, "resume", {}, Context(), "xx") == "Turned all notifications back on"
    assert "non conosce" in await async_respond(engine, "dance", {}, Context(), "it")


async def test_italian_notify_asks_which_when_first_name_shared(hass: HomeAssistant) -> None:
    engine, calls = await _setup(hass, extra_people={"person.jey_smith": "Jey Smith"})

    response = await async_respond(engine, "notify", {"name": "Jey", "message": "ciao"}, Context(), "it")

    assert response == "Quale Jey intendi: Jey Burrows o Jey Smith?"
    assert calls == []
