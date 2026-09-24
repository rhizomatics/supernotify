"""Sentences for Home Assistant's built-in conversation agent (sentences.py)

The agent itself needs hassil and the rest of the voice stack, so it isn't run here - the
commands are called directly, and the trigger registration is checked with it patched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import CONF_LLM_TOOLS, CONF_SENTENCE_COMMANDS
from custom_components.supernotify.model import GlobalTargetType, RecipientType
from custom_components.supernotify.sentences import SENTENCES, async_respond

if TYPE_CHECKING:
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
    assert {c["id"]: c["command"] for c in configs} == SENTENCES
    assert all(c["platform"] == "conversation" for c in configs)

    action = initialize.call_args.args[2]
    result = await action({
        "trigger": {
            "id": "notify",
            "slots": {"name": "Bob", "message": "the post has come"},
            "user_input": {"context": {"id": "abc", "user_id": JEY_USER_ID}},
        }
    })
    assert result.conversation_response == "Sent to Bob"
    assert calls[0].context.user_id == JEY_USER_ID

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
