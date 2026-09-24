"""The beta LLM tools offered to Assist conversation agents and the MCP server (llm.py)"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import CONF_LLM_ACTION_TOOLS, CONF_LLM_DIAGNOSTIC_TOOLS, CONF_LLM_TOOLS
from custom_components.supernotify.model import GlobalTargetType, QualifiedTargetType, RecipientType

# the llm platform and probatio are only in the newer Home Assistant installed for py3.14 - drop with py3.13
pytest.importorskip("homeassistant.components.llm")

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_homeassistant_custom_component.test_util.aiohttp import (  # type: ignore[import-untyped,unused-ignore]
        AiohttpClientMocker,
    )

    from custom_components.supernotify.engine import SupernotifyEngine

ALICE_USER_ID = "alice-user-id"
ACTION_TOOLS = {"supernotify__notify", "supernotify__snooze"}
DIAGNOSTIC_TOOLS = {
    "supernotify__recent_notifications",
    "supernotify__dry_run",
    "supernotify__snoozes",
    "supernotify__help",
}


def _config(archive_path: Path | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {
        "delivery": {
            "chat": {
                "alias": "Family chat",
                "transport": "generic",
                "action": "testing.mock_notification",
                "inclusion": ["default"],
            },
            "urgent": {
                "transport": "generic",
                "action": "testing.mock_notification",
                "priority": ["critical", "high"],
                "inclusion": ["default"],
            },
        },
        "recipients": [{"person": "person.alice", "email": "alice@example.com"}, {"person": "person.bob"}],
        "scenarios": {"night": {"alias": "Night time"}},
    }
    if archive_path:
        config["archive"] = {"enabled": True, "file_path": str(archive_path)}
    return config


async def _setup(
    hass: HomeAssistant,
    action_tools: bool = True,
    diagnostic_tools: bool = True,
    archive_path: Path | None = None,
) -> tuple[SupernotifyEngine, list[ServiceCall]]:
    calls: list[ServiceCall] = []

    async def _mock_notification(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("testing", "mock_notification", _mock_notification)
    hass.states.async_set("person.alice", "home", {"friendly_name": "Alice", "user_id": ALICE_USER_ID})
    hass.states.async_set("person.bob", "not_home", {"friendly_name": "Bob"})
    assert await async_setup_component(hass, "llm", {})
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: _config(archive_path)})
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_LLM_TOOLS: {CONF_LLM_ACTION_TOOLS: action_tools, CONF_LLM_DIAGNOSTIC_TOOLS: diagnostic_tools},
        },
    )
    await hass.async_block_till_done()
    return entry.runtime_data, calls


async def _api(hass: HomeAssistant, user_id: str | None = None) -> llm.APIInstance:
    return await llm.async_get_api(
        hass,
        llm.LLM_API_ASSIST,
        llm.LLMContext(
            platform="test", context=Context(user_id=user_id), language="en", assistant="conversation", device_id=None
        ),
    )


async def _call(hass: HomeAssistant, tool: str, args: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    # what APIInstance.async_call_tool() does, less its conversation trace - importing the
    # conversation integration for that needs hassil and the rest of the voice stack
    api = await _api(hass, user_id)
    found = next(t for t in api.tools if t.name == tool)
    return dict(await found.async_call(hass, llm.ToolInput(tool_name=tool, tool_args=args), api.llm_context))


def _supernotify_tools(api: llm.APIInstance) -> set[str]:
    return {tool.name for tool in api.tools if tool.name.startswith("supernotify__")}


async def test_no_tools_until_switched_on(hass: HomeAssistant) -> None:
    await _setup(hass, action_tools=False, diagnostic_tools=False)

    assert _supernotify_tools(await _api(hass)) == set()


@pytest.mark.parametrize(
    ("action_tools", "diagnostic_tools", "expected"),
    [(True, False, ACTION_TOOLS), (False, True, DIAGNOSTIC_TOOLS), (True, True, ACTION_TOOLS | DIAGNOSTIC_TOOLS)],
)
async def test_tools_switched_on_separately(
    hass: HomeAssistant, action_tools: bool, diagnostic_tools: bool, expected: set[str]
) -> None:
    await _setup(hass, action_tools=action_tools, diagnostic_tools=diagnostic_tools)

    assert _supernotify_tools(await _api(hass)) == expected


async def test_tool_parameters_serialize_for_llms(hass: HomeAssistant) -> None:
    await _setup(hass)
    api = await _api(hass)

    for tool in api.tools:
        if tool.name.startswith("supernotify__"):
            from probatio import to_openapi

            # how the MCP server, and conversation agents, describe a tool's parameters to the model
            to_openapi(tool.parameters, custom_serializer=api.custom_serializer)


async def test_prompt_lists_configured_names(hass: HomeAssistant) -> None:
    await _setup(hass)

    prompt = (await _api(hass)).api_prompt

    assert "chat (Family chat)" in prompt
    assert "night (Night time)" in prompt
    assert "Alice, Bob" in prompt


async def test_notify_offers_only_configured_choices(hass: HomeAssistant) -> None:
    await _setup(hass)
    tool = next(t for t in (await _api(hass)).tools if t.name == "supernotify__notify")

    for field in ("custom_target", "actions", "media", "snapshot_url", "clip_url", "target"):
        with pytest.raises(vol.Invalid):
            tool.parameters({"message": "hi", field: "anything"})
    with pytest.raises(vol.Invalid):
        tool.parameters({"message": "hi", "recipients": ["mallory@example.com"]})
    with pytest.raises(vol.Invalid):
        tool.parameters({"message": "hi", "deliveries": ["not_configured"]})


async def test_notify_sends_to_named_recipient(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass)

    result = await _call(hass, "supernotify__notify", {"message": "Dinner is ready", "recipients": ["Alice"]})

    assert result["success"] is True
    assert result["result"]["message"] == "Dinner is ready"
    assert result["result"]["deliveries"]["chat"]["success"] == 1
    assert result["result"]["deliveries"]["urgent"] == {"skipped": "PRIORITY"}
    assert [c.data["message"] for c in calls] == ["Dinner is ready"]


async def test_notify_allows_critical_priority(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass)

    result = await _call(hass, "supernotify__notify", {"message": "Smoke alarm", "priority": "critical"})

    assert result["success"] is True
    assert result["result"]["priority"] == "critical"
    assert result["result"]["deliveries"]["urgent"]["success"] == 1
    assert len(calls) == 2


async def test_notify_passes_on_callers_context(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass)

    await _call(hass, "supernotify__notify", {"message": "hi", "deliveries": ["chat"]}, user_id=ALICE_USER_ID)

    assert calls[0].context.user_id == ALICE_USER_ID


async def test_snooze_defaults_to_person_asking(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    result = await _call(
        hass,
        "supernotify__snooze",
        {"action": "snooze", "scope": "delivery", "name": "chat", "minutes": 30},
        user_id=ALICE_USER_ID,
    )

    assert result["success"] is True
    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.target_type == QualifiedTargetType.DELIVERY
    assert snooze.target == "chat"
    assert snooze.recipient_type == RecipientType.USER
    assert snooze.recipient == "person.alice"
    assert snooze.snooze_until is not None
    assert dt.timedelta(minutes=29) < snooze.snooze_until - snooze.snoozed_at <= dt.timedelta(minutes=30)


async def test_snooze_everyone_when_asker_unknown(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    await _call(hass, "supernotify__snooze", {"action": "silence", "scope": "noncritical"})

    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.target_type == GlobalTargetType.NONCRITICAL
    assert snooze.recipient_type == RecipientType.EVERYONE
    assert snooze.snooze_until is None


async def test_snooze_named_recipient(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)

    await _call(hass, "supernotify__snooze", {"action": "snooze", "recipient": "Bob"}, user_id=ALICE_USER_ID)

    [snooze] = engine.context.snoozer.snoozes.values()
    assert snooze.recipient == "person.bob"


async def test_unsnooze_and_clear_all(hass: HomeAssistant) -> None:
    engine, _calls = await _setup(hass)
    await _call(hass, "supernotify__snooze", {"action": "silence", "scope": "priority", "name": "low"})
    await _call(hass, "supernotify__snooze", {"action": "silence", "scope": "transport", "name": "generic"})

    await _call(hass, "supernotify__snooze", {"action": "unsnooze", "scope": "priority", "name": "low"})
    assert [s.target for s in engine.context.snoozer.snoozes.values()] == ["generic"]

    result = await _call(hass, "supernotify__snooze", {"action": "clear_all"})
    assert result["result"] == {"cleared": 1}
    assert engine.context.snoozer.snoozes == {}


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"scope": "delivery"}, "A name is needed"),
        ({"scope": "delivery", "name": "fax"}, "Unknown delivery 'fax'"),
        ({"scope": "priority", "name": "whenever"}, "Unknown priority 'whenever'"),
        ({"scope": "camera", "name": "front door"}, "entity_id"),
    ],
)
async def test_snooze_rejects_unknown_names(hass: HomeAssistant, args: dict[str, Any], error: str) -> None:
    engine, _calls = await _setup(hass)

    result = await _call(hass, "supernotify__snooze", {"action": "snooze", **args})

    assert result["success"] is False
    assert error in result["error"]
    assert engine.context.snoozer.snoozes == {}


async def test_snoozes_lists_current(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _call(hass, "supernotify__snooze", {"action": "silence", "scope": "camera", "name": "camera.porch"})

    result = await _call(hass, "supernotify__snoozes", {})

    [snooze] = result["result"]["snoozes"]
    assert snooze["target"] == "camera.porch"


async def test_dry_run_sends_nothing(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass)

    result = await _call(hass, "supernotify__dry_run", {"message": "Alarm", "recipients": ["Alice"]})

    plan = result["result"]
    assert calls == []
    assert plan["deliveries"]["chat"]["recipients"] == ["Alice"]
    assert plan["deliveries"]["chat"]["targets"] == [{"email": ["al***m"]}]
    assert plan["deliveries"]["urgent"] == {"skipped": "PRIORITY"}
    assert plan["occupancy"] == {"home": ["Alice"], "not_home": ["Bob"]}
    assert plan["delivery_provenance"]["chat"] == {"enabled_by": ["default"]}


async def test_dry_run_leaves_dupe_check_alone(hass: HomeAssistant) -> None:
    _engine, calls = await _setup(hass)

    await _call(hass, "supernotify__dry_run", {"message": "Alarm", "deliveries": ["chat"]})
    result = await _call(hass, "supernotify__notify", {"message": "Alarm", "deliveries": ["chat"]})

    assert result["success"] is True
    assert len(calls) == 1


async def test_dry_run_reports_snoozed_delivery(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _call(
        hass, "supernotify__snooze", {"action": "silence", "scope": "delivery", "name": "chat", "recipient": "everyone"}
    )

    result = await _call(hass, "supernotify__dry_run", {"deliveries": ["chat"]})

    assert result["result"]["deliveries"] == {"chat": {"skipped": "SNOOZED"}}
    assert result["result"]["fallback"] == []


async def test_dry_run_reports_global_suppression(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _call(hass, "supernotify__snooze", {"action": "silence", "recipient": "everyone"})

    result = await _call(hass, "supernotify__dry_run", {})

    assert result["result"]["suppressed"] == "SNOOZED"
    assert result["result"]["deliveries"] == {}


async def test_recent_notifications_without_archive(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _call(hass, "supernotify__notify", {"message": "first", "deliveries": ["chat"]})
    await _call(hass, "supernotify__notify", {"message": "second", "deliveries": ["chat"]})

    result = await _call(hass, "supernotify__recent_notifications", {})

    assert "archive is off" in result["result"]["note"]
    assert [n["message"] for n in result["result"]["notifications"]] == ["second"]


async def test_recent_notifications_from_archive(hass: HomeAssistant, tmp_path: Path) -> None:
    await _setup(hass, archive_path=tmp_path)
    await _call(hass, "supernotify__notify", {"message": "for alice", "recipients": ["Alice"]})
    await _call(hass, "supernotify__notify", {"message": "for bob", "recipients": ["Bob"]})
    await _call(hass, "supernotify__notify", {"message": "for everyone"})

    everything = await _call(hass, "supernotify__recent_notifications", {})
    for_alice = await _call(hass, "supernotify__recent_notifications", {"recipient": "Alice"})
    limited = await _call(hass, "supernotify__recent_notifications", {"limit": 1})

    assert "note" not in everything["result"]
    assert {n["message"] for n in everything["result"]["notifications"]} == {"for alice", "for bob", "for everyone"}
    assert {n["message"] for n in for_alice["result"]["notifications"]} == {"for alice", "for everyone"}
    assert len(limited["result"]["notifications"]) == 1
    summary = next(n for n in for_alice["result"]["notifications"] if n["message"] == "for alice")
    assert summary["deliveries"]["chat"] == {"success": 1, "recipients": ["Alice"]}
    assert summary["occupancy"] == {"home": ["Alice"], "not_home": ["Bob"]}


DOCS = """# Home Assistant Supernotify

Preamble

# Snoozing

Snoozing can be selected from a mobile action, and made for a set time.

# Recipe - Alexa Whispering

Make Alexa whisper low priority notifications.

```yaml
# a comment in an example

delivery:
  alexa_whisper:
    transport: alexa_devices
```

# Recipe - Email CC

Copy every e-mail to one address.
"""
DOCS_INDEX = """# Home Assistant Supernotify

## Using Supernotify

- [Snoozing](https://example.org/latest/usage/snoozing/index.md)

## Recipes

- [Alexa Whispering Low Priority Announcements](https://example.org/latest/recipes/alexa_whisper/index.md)
"""


def test_split_docs_by_page() -> None:
    from custom_components.supernotify.llm import split_docs

    pages = split_docs(DOCS, DOCS_INDEX)

    assert [(p.title, p.url) for p in pages] == [
        ("Home Assistant Supernotify", None),
        ("Snoozing", "https://example.org/latest/usage/snoozing/"),
        ("Recipe - Alexa Whispering", "https://example.org/latest/recipes/alexa_whisper/"),
        ("Recipe - Email CC", None),
    ]
    assert "# a comment in an example" in pages[2].text


def test_search_docs_prefers_title_and_matches_stems() -> None:
    from custom_components.supernotify.llm import search_docs, split_docs

    pages = split_docs(DOCS, DOCS_INDEX)

    assert [p.title for p in search_docs(pages, "how do I snooze a notification?")] == ["Snoozing"]
    assert next(p.title for p in search_docs(pages, "make alexa whisper")) == "Recipe - Alexa Whispering"
    assert search_docs(pages, "the notification") == []


async def test_help_fetches_docs_once_and_answers(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.supernotify.llm import DOCS_INDEX_URL, DOCS_URL

    aioclient_mock.get(DOCS_URL, text=DOCS)
    aioclient_mock.get(DOCS_INDEX_URL, text=DOCS_INDEX)
    await _setup(hass)

    result = await _call(hass, "supernotify__help", {"question": "snoozing from a phone"})
    await _call(hass, "supernotify__help", {"question": "alexa"})

    assert result["success"] is True
    [page] = result["result"]["pages"]
    assert page["title"] == "Snoozing"
    assert page["url"] == "https://example.org/latest/usage/snoozing/"
    assert page["text"].startswith("Snoozing can be selected")
    assert aioclient_mock.call_count == 2


async def test_help_without_index_still_answers(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.supernotify.llm import DOCS_INDEX_URL, DOCS_URL

    aioclient_mock.get(DOCS_URL, text=DOCS)
    aioclient_mock.get(DOCS_INDEX_URL, status=404)
    await _setup(hass)

    result = await _call(hass, "supernotify__help", {"question": "snoozing"})

    assert result["result"]["pages"][0]["url"] is None


async def test_help_nothing_matched(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.supernotify.llm import DOCS_INDEX_URL, DOCS_URL

    aioclient_mock.get(DOCS_URL, text=DOCS)
    aioclient_mock.get(DOCS_INDEX_URL, text=DOCS_INDEX)
    await _setup(hass)

    result = await _call(hass, "supernotify__help", {"question": "zeppelin"})

    assert result["result"]["pages"] == []
    assert "Nothing matched" in result["result"]["note"]


async def test_help_site_unreachable(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    from custom_components.supernotify.llm import DOCS_URL

    aioclient_mock.get(DOCS_URL, exc=TimeoutError())
    await _setup(hass)

    result = await _call(hass, "supernotify__help", {"question": "snoozing"})

    assert result["success"] is False
    assert "could not be reached" in result["error"]
