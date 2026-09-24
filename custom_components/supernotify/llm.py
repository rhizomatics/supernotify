"""LLM tools for Assist conversation agents and Home Assistant's MCP server - beta.

Home Assistant's `llm` integration merges the tools from every integration's `llm` platform into
its built-in Assist API, which is also what the MCP server offers by default. Nothing here is
offered until switched on in the Supernotify options, where action tools (send, snooze) and
diagnostic tools (recent notifications, dry run, snoozes, documentation) are switched on separately.

The tools deliberately leave out Supernotify's more open-ended fields - `custom_target` (any
e-mail address, phone number etc), `actions`, and media URLs - so an agent can only reach the
recipients, deliveries and scenarios already configured.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

import aiohttp
import voluptuous as vol
from homeassistant.components.llm import LLMTools  # type: ignore[import-not-found,unused-ignore]  # HA < 2026.x on py3.13
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.llm import LLM_API_ASSIST, LLMContext, Tool, ToolInput
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from . import DOMAIN
from .const import (
    ATTR_DELIVERY,
    ATTR_PRIORITY,
    ATTR_SCENARIOS_APPLY,
    CONF_LLM_ACTION_TOOLS,
    CONF_LLM_DIAGNOSTIC_TOOLS,
    CONF_LLM_TOOLS,
    PRIORITY_VALUES,
)
from .model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType, TargetType

if TYPE_CHECKING:
    from homeassistant.util.json import JsonObjectType

    from .engine import SupernotifyEngine
    from .people import Recipient

_LOGGER = logging.getLogger(__name__)

EVERYONE = "everyone"
MAX_HOURS = 7 * 24
MAX_NOTIFICATIONS = 50

# The documentation site publishes every page as one markdown file for LLMs, plus an index with links
DOCS_SITE = "https://supernotify.rhizomatics.org.uk/"
DOCS_URL = f"{DOCS_SITE}llms-full.txt"
DOCS_INDEX_URL = f"{DOCS_SITE}llms.txt"
DOCS_CACHE_TIME = dt.timedelta(days=1)
# the line under each page title giving its link, from docgen/llms_preprocess.py
DOCS_SOURCE_PREFIX = "Source: "
DOCS_SECTIONS_RETURNED = 3
DOCS_SECTION_MAX_CHARS = 4000
DOCS_STOP_WORDS = frozenset([
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "using",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    # words in almost every page of these docs
    "notification",
    "notifications",
    "notify",
    "supernotify",
    "send",
])


@dataclass
class DocsPage:
    title: str
    url: str | None
    text: str


@dataclass
class _DocsCache:
    fetched: dt.datetime
    pages: list[DocsPage]


DOCS_CACHE: HassKey[_DocsCache] = HassKey(f"{DOMAIN}_llm_docs")

SNOOZE_ACTIONS: dict[str, CommandType | None] = {
    "snooze": CommandType.SNOOZE,
    "silence": CommandType.SILENCE,
    "unsnooze": CommandType.NORMAL,
    "clear_all": None,
}
SNOOZE_SCOPES: dict[str, TargetType] = {
    "everything": GlobalTargetType.EVERYTHING,
    "noncritical": GlobalTargetType.NONCRITICAL,
    "delivery": QualifiedTargetType.DELIVERY,
    "transport": QualifiedTargetType.TRANSPORT,
    "priority": QualifiedTargetType.PRIORITY,
    "camera": QualifiedTargetType.CAMERA,
}


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext, api_id: str) -> LLMTools | None:
    """Return the Supernotify tools switched on in the options, rebuilt each time so the
    choices offered for deliveries, scenarios and recipients are always the current ones."""
    if api_id != LLM_API_ASSIST:
        return None
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None
    engine: SupernotifyEngine = entries[0].runtime_data
    options: dict[str, Any] = entries[0].options.get(CONF_LLM_TOOLS, {})
    tools: list[Tool] = []
    if options.get(CONF_LLM_ACTION_TOOLS):
        tools.extend([NotifyTool(engine), SnoozeTool(engine)])
    if options.get(CONF_LLM_DIAGNOSTIC_TOOLS):
        tools.extend([RecentNotificationsTool(engine), DryRunTool(engine), SnoozesTool(engine), HelpTool(engine)])
    if not tools:
        return None
    return LLMTools(tools=tools, prompt=_prompt(engine))


def _prompt(engine: SupernotifyEngine) -> str:
    context = engine.context
    lines = ["Supernotify sends notifications to the household by phone, e-mail, speakers and other ways."]
    if deliveries := [_labelled(name, d.alias) for name, d in context.delivery_registry.deliveries.items()]:
        lines.append(f"Deliveries: {', '.join(deliveries)}.")
    if scenarios := [_labelled(name, s.alias) for name, s in context.scenario_registry.scenarios.items()]:
        lines.append(f"Scenarios: {', '.join(scenarios)}.")
    if recipients := _recipient_names(engine):
        lines.append(f"Recipients: {', '.join(recipients)}.")
    return "\n".join(lines)


def _labelled(name: str, alias: str | None) -> str:
    return f"{name} ({alias})" if alias and alias != name else name


def _display_name(recipient: Recipient) -> str:
    return recipient.alias or recipient.name


def _recipient_names(engine: SupernotifyEngine) -> list[str]:
    return sorted(_display_name(r) for r in engine.context.people_registry.enabled_recipients())


def _person_id(engine: SupernotifyEngine, name: str) -> str | None:
    return engine.context.people_registry.person_id_for_name(name)


def _names_for(engine: SupernotifyEngine, person_ids: list[str]) -> list[str]:
    people = engine.context.people_registry.people
    return sorted(_display_name(people[p]) if p in people else p for p in person_ids)


def _notification_fields(engine: SupernotifyEngine, message_required: bool) -> dict[vol.Marker, Any]:
    """The notification fields an agent may use - never custom_target, actions or media URLs"""
    context = engine.context
    fields: dict[vol.Marker, Any] = {
        (vol.Required if message_required else vol.Optional)("message", description="The notification text"): str,
        vol.Optional("title", description="A short title, used by deliveries that show one"): str,
        vol.Optional("priority", description="How urgent the notification is, which decides which deliveries are used"): vol.In(
            list(PRIORITY_VALUES)
        ),
    }
    if recipients := _recipient_names(engine):
        fields[vol.Optional("recipients", description="Who to notify. Leave out to use the usual recipients")] = [
            vol.In(recipients)
        ]
    if deliveries := list(context.delivery_registry.deliveries):
        fields[vol.Optional("deliveries", description="Use only these deliveries. Leave out to choose automatically")] = [
            vol.In(deliveries)
        ]
    if scenarios := list(context.scenario_registry.scenarios):
        fields[vol.Optional("scenarios", description="Scenarios to apply, as if their conditions were met")] = [
            vol.In(scenarios)
        ]
    return fields


def _notification_call(engine: SupernotifyEngine, args: dict[str, Any]) -> tuple[list[str] | None, dict[str, Any], list[str]]:
    """Turn tool arguments into a target list and action data, plus any recipient names not known"""
    person_ids: list[str] = []
    unknown: list[str] = []
    for name in args.get("recipients", []):
        if person_id := _person_id(engine, name):
            person_ids.append(person_id)
        else:
            unknown.append(name)
    data: dict[str, Any] = {}
    if "priority" in args:
        data[ATTR_PRIORITY] = args["priority"]
    if args.get("deliveries"):
        data[ATTR_DELIVERY] = args["deliveries"]
    if args.get("scenarios"):
        data[ATTR_SCENARIOS_APPLY] = args["scenarios"]
    return person_ids or None, data, unknown


def summarize_notification(engine: SupernotifyEngine, contents: dict[str, Any]) -> dict[str, Any]:
    """Cut an archived or live notification down to what explains what happened to it"""
    deliveries: dict[str, dict[str, Any]] = {}
    for name, outcomes in (contents.get("deliveries") or {}).items():
        if skipped := outcomes.get("skipped"):
            deliveries[name] = {"skipped": skipped.get("suppression_reason")}
            continue
        summary: dict[str, Any] = {}
        recipients: set[str] = set()
        for outcome in ("success", "suppressed", "error"):
            envelopes: list[dict[str, Any]] = outcomes.get(outcome) or []
            if not envelopes:
                continue
            summary[outcome] = len(envelopes)
            for envelope in envelopes:
                recipients.update(((envelope.get("target") or {}).get("person_id")) or [])
                if outcome == "suppressed" and envelope.get("skip_reason"):
                    summary.setdefault("reasons", []).append(envelope["skip_reason"])
                if outcome == "error":
                    summary.setdefault("errors", []).extend(
                        call.get("exception") for call in envelope.get("failed_calls") or [] if call.get("exception")
                    )
        if recipients:
            summary["recipients"] = _names_for(engine, sorted(recipients))
        deliveries[name] = summary
    condition_variables: dict[str, Any] = contents.get("condition_variables") or {}
    result: dict[str, Any] = {
        "id": contents.get("id"),
        "created": contents.get("created"),
        "outcome": contents.get("outcome"),
        "message": contents.get("message"),
        "title": condition_variables.get("notification_title"),
        "priority": contents.get("priority"),
        "scenarios": contents.get("enabled_scenarios") or [],
        "occupancy": {
            state: _names_for(engine, [p.get("person") for p in people if p.get("person")])
            for state, people in (contents.get("occupancy") or {}).items()
        },
        "deliveries": deliveries,
        "delivery_provenance": contents.get("delivery_provenance") or {},
    }
    if contents.get("unknown_names"):
        result["unknown_names"] = contents["unknown_names"]
    if contents.get("_suppression_reason"):
        result["suppressed"] = contents["_suppression_reason"]
    if requester := (contents.get("original_context") or {}).get("user"):
        result["requested_by"] = requester
    return result


class SupernotifyTool(Tool):
    def __init__(self, engine: SupernotifyEngine) -> None:
        self.engine = engine


class NotifyTool(SupernotifyTool):
    name = "supernotify__notify"
    description = (
        "Send a notification to people in the household, e.g. 'tell everyone dinner is ready' or "
        "'send Alice an urgent message'. Supernotify chooses how to reach each person from the priority, "
        "the active scenarios and who is home, unless deliveries are given."
    )

    def __init__(self, engine: SupernotifyEngine) -> None:
        super().__init__(engine)
        self.parameters = vol.Schema(_notification_fields(engine, message_required=True))

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        args = self.parameters(tool_input.tool_args)
        target, data, unknown = _notification_call(self.engine, args)
        if unknown:
            return {"success": False, "error": f"Unknown recipients: {', '.join(unknown)}"}
        notification = await self.engine.async_send_message(
            args["message"], title=args.get("title"), target=target, data=data, context=llm_context.context
        )
        if notification is None:
            return {"success": False, "error": "The notification could not be created"}
        return {
            "success": notification.delivered > 0,
            "result": summarize_notification(self.engine, notification.contents()),
        }


class SnoozeTool(SupernotifyTool):
    name = "supernotify__snooze"
    description = (
        "Snooze or silence notifications, or turn them back on, e.g. 'mute the doorbell camera alerts for an hour' "
        "or 'stop non-urgent notifications until I say'. 'snooze' lasts for the given minutes, 'silence' until "
        "undone, 'unsnooze' undoes one snooze, and 'clear_all' removes every snooze for everyone."
    )

    def __init__(self, engine: SupernotifyEngine) -> None:
        super().__init__(engine)
        self.parameters = vol.Schema({
            vol.Required("action"): vol.In(list(SNOOZE_ACTIONS)),
            vol.Optional("scope", default="everything", description="What kind of notifications to snooze"): vol.In(
                list(SNOOZE_SCOPES)
            ),
            vol.Optional(
                "name",
                description="The delivery, transport, priority or camera entity_id to snooze, when scope is one of those",
            ): str,
            vol.Optional(
                "recipient",
                description="Whose notifications to snooze. Leave out for the person asking, or everyone if unknown",
            ): vol.In([*_recipient_names(engine), EVERYONE]),
            vol.Optional("minutes", description="How long to snooze for"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_HOURS * 60)
            ),
        })

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        args = self.parameters(tool_input.tool_args)
        snoozer = self.engine.context.snoozer
        cmd: CommandType | None = SNOOZE_ACTIONS[args["action"]]
        if cmd is None:
            return {"success": True, "result": {"cleared": self.engine.clear_snoozes()}}

        scope: TargetType = SNOOZE_SCOPES[args["scope"]]
        name: str | None = args.get("name")
        if isinstance(scope, QualifiedTargetType):
            if error := self._check_name(scope, name):
                return {"success": False, "error": error}
        else:
            name = None

        recipient: str | None = None
        recipient_name: str | None = args.get("recipient")
        if recipient_name is None:
            recipient = self._requesting_person(llm_context)
        elif recipient_name != EVERYONE:
            recipient = _person_id(self.engine, recipient_name)
        recipient_type = RecipientType.USER if recipient else RecipientType.EVERYONE

        minutes: int | None = args.get("minutes")
        snooze_for = dt.timedelta(minutes=minutes) if minutes else snoozer.snooze_period
        snoozer.register_snooze(cmd, scope, name, recipient_type, recipient, snooze_for, reason="Assistant")
        snoozes: dict[str, Any] = {"snoozes": self.engine.enquire_snoozes()}
        return {"success": True, "result": snoozes}

    def _check_name(self, scope: QualifiedTargetType, name: str | None) -> str | None:
        registry = self.engine.context.delivery_registry
        valid: list[str] | None = {
            QualifiedTargetType.DELIVERY: list(registry.deliveries),
            QualifiedTargetType.TRANSPORT: list(registry.transports),
            QualifiedTargetType.PRIORITY: list(PRIORITY_VALUES),
        }.get(scope)
        if not name:
            return f"A name is needed to snooze a {scope.lower()}"
        if valid is not None and name not in valid:
            return f"Unknown {scope.lower()} '{name}', choose from: {', '.join(valid)}"
        if scope == QualifiedTargetType.CAMERA and not name.startswith("camera."):
            return "A camera must be given as its entity_id, e.g. camera.front_door"
        return None

    def _requesting_person(self, llm_context: LLMContext) -> str | None:
        user_id: str | None = llm_context.context.user_id if llm_context.context else None
        return self.engine.context.people_registry.person_id_for_user_id(user_id)


class RecentNotificationsTool(SupernotifyTool):
    name = "supernotify__recent_notifications"
    description = (
        "List recent notifications and what happened to each one: which deliveries sent, were skipped or failed, "
        "and why. Use this for questions like 'why didn't I get the doorbell alert?' or 'what notifications went "
        "out today?'. 'occupancy' shows who was home at the time, which decides some deliveries."
    )

    def __init__(self, engine: SupernotifyEngine) -> None:
        super().__init__(engine)
        fields: dict[vol.Marker, Any] = {
            vol.Optional("hours", default=24, description="How many hours back to look"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_HOURS)
            ),
            vol.Optional("limit", default=10, description="The most notifications to return, newest first"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_NOTIFICATIONS)
            ),
        }
        if recipients := _recipient_names(engine):
            fields[vol.Optional("recipient", description="Only notifications that reached this person")] = vol.In(recipients)
        self.parameters = vol.Schema(fields)

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        args = self.parameters(tool_input.tool_args)
        since: dt.datetime = dt_util.now() - dt.timedelta(hours=args["hours"])
        archive = self.engine.context.archive
        result: dict[str, Any] = {}
        if archive.archive_directory and archive.archive_directory.enabled:
            archived = await archive.recent(since, MAX_NOTIFICATIONS)
        else:
            last = self.engine.last_notification
            archived = [last.contents()] if last and last.created >= since else []
            result["note"] = (
                "The notification archive is off, so only the latest notification since Home Assistant started "
                "is known. It can be turned on in the Supernotify options."
            )
        summaries = [summarize_notification(self.engine, contents) for contents in archived]
        if recipient := args.get("recipient"):
            summaries = [s for s in summaries if any(recipient in d.get("recipients", []) for d in s["deliveries"].values())]
        result["notifications"] = summaries[: args["limit"]]
        return {"success": True, "result": result}


class DryRunTool(SupernotifyTool):
    name = "supernotify__dry_run"
    description = (
        "Work out who a notification would reach right now, and by which deliveries, without sending it. "
        "Use this for questions like 'if the alarm goes off, who gets told and how?'. 'occupancy' shows who is "
        "home, which decides some deliveries. The duplicate check is not made."
    )

    def __init__(self, engine: SupernotifyEngine) -> None:
        super().__init__(engine)
        self.parameters = vol.Schema(_notification_fields(engine, message_required=False))

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        args = self.parameters(tool_input.tool_args)
        target, data, unknown = _notification_call(self.engine, args)
        if unknown:
            return {"success": False, "error": f"Unknown recipients: {', '.join(unknown)}"}
        plan = await self.engine.async_dry_run(args.get("message", ""), title=args.get("title"), target=target, data=data)
        plan["occupancy"] = {state: _names_for(self.engine, people) for state, people in plan["occupancy"].items()}
        for delivery in plan["deliveries"].values():
            if "recipients" in delivery:
                delivery["recipients"] = _names_for(self.engine, delivery["recipients"])
        return {"success": True, "result": plan}


class SnoozesTool(SupernotifyTool):
    name = "supernotify__snoozes"
    description = "List the notification snoozes and silences in place, and who they apply to."

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        snoozes: dict[str, Any] = {"snoozes": self.engine.enquire_snoozes()}
        return {"success": True, "result": snoozes}


def split_docs(text: str, index: str = "") -> list[DocsPage]:
    """Split the combined documentation into pages, each starting at a top level heading with a
    blank line either side - which a comment in a code example rarely has. Each page's link is its
    own "Source:" line, published since v2.10.0, else taken from the index where the titles match"""
    urls: dict[str, str] = {
        title.casefold(): url.removesuffix("index.md")
        for title, url in re.findall(r"^- \[([^\]]+)\]\(([^)]+)\)", index, flags=re.MULTILINE)
    }
    pages: list[DocsPage] = []
    title: str | None = None
    lines: list[str] = text.splitlines()
    body: list[str] = []

    def url_for(page_title: str) -> str | None:
        # recipe pages are titled "Recipe - X", where the index often has a longer "X ..."
        wanted = page_title.casefold().removeprefix("recipe - ")
        return urls.get(wanted) or next((u for t, u in urls.items() if t.startswith(wanted)), None)

    def finish() -> None:
        if title and (page_text := "\n".join(body).strip()):
            first_line, _, rest = page_text.partition("\n")
            if first_line.startswith(DOCS_SOURCE_PREFIX):
                pages.append(DocsPage(title, first_line.removeprefix(DOCS_SOURCE_PREFIX).strip(), rest.strip()))
            else:
                pages.append(DocsPage(title, url_for(title), page_text))

    for i, line in enumerate(lines):
        if line.startswith("# ") and (i == 0 or not lines[i - 1].strip()) and (i + 1 == len(lines) or not lines[i + 1].strip()):
            finish()
            title, body = line[2:].strip(), []
        else:
            body.append(line)
    finish()
    return pages


def search_docs(pages: list[DocsPage], question: str) -> list[DocsPage]:
    """The pages that best match the question - most of all in the title, then by how many of its
    words they contain, then by how densely, so a long page doesn't win just by being long.
    Words are matched by their stem, so 'snooze' finds 'Snoozing'."""
    stems = {
        w[: max(4, len(w) - 3)]
        for w in re.findall(r"[a-z0-9_]+", question.casefold())
        if len(w) > 2 and w not in DOCS_STOP_WORDS
    }
    scored: list[tuple[float, int, DocsPage]] = []
    for position, page in enumerate(pages):
        title, text = page.title.casefold(), page.text.casefold()
        score = 0.0
        for stem in stems:
            if count := text.count(stem):
                score += 2 + min(count * 1000 / len(text), 3)
            if stem in title:
                score += 6
        if score:
            scored.append((-score, position, page))
    return [page for _score, _position, page in sorted(scored)[:DOCS_SECTIONS_RETURNED]]


async def _docs(hass: HomeAssistant) -> list[DocsPage]:
    """The documentation pages, fetched on first use and then at most once a day"""
    cached: _DocsCache | None = hass.data.get(DOCS_CACHE)
    if cached and dt_util.utcnow() - cached.fetched < DOCS_CACHE_TIME:
        return cached.pages
    session = async_get_clientsession(hass)
    timeout = aiohttp.ClientTimeout(total=15)
    async with session.get(DOCS_URL, timeout=timeout) as response:
        response.raise_for_status()
        text = await response.text()
    index = ""
    try:
        async with session.get(DOCS_INDEX_URL, timeout=timeout) as response:
            response.raise_for_status()
            index = await response.text()
    except (aiohttp.ClientError, TimeoutError) as e:
        _LOGGER.debug("SUPERNOTIFY Documentation index not fetched, pages will have no links: %s", e)
    pages = split_docs(text, index)
    hass.data[DOCS_CACHE] = _DocsCache(dt_util.utcnow(), pages)
    return pages


class HelpTool(SupernotifyTool):
    name = "supernotify__help"
    description = (
        "Look up the Supernotify documentation, for how-to questions such as 'how do I e-mail a camera snapshot?' "
        "or 'what does inclusion fallback mean?'. Returns the best matching pages, with configuration examples "
        "and recipes, to answer from. The documentation is for the latest release, in English."
    )

    def __init__(self, engine: SupernotifyEngine) -> None:
        super().__init__(engine)
        self.parameters = vol.Schema({
            vol.Required("question", description="What to look up, in a few words or a whole question"): str
        })

    @override
    async def async_call(self, hass: HomeAssistant, tool_input: ToolInput, llm_context: LLMContext) -> JsonObjectType:
        args = self.parameters(tool_input.tool_args)
        try:
            pages = await _docs(hass)
        except (aiohttp.ClientError, TimeoutError) as e:
            _LOGGER.warning("SUPERNOTIFY Unable to fetch documentation from %s: %s", DOCS_URL, e)
            return {"success": False, "error": f"The documentation site could not be reached ({e})"}
        found: dict[str, Any] = {
            "site": DOCS_SITE,
            "pages": [
                {"title": page.title, "url": page.url, "text": page.text[:DOCS_SECTION_MAX_CHARS]}
                for page in search_docs(pages, args["question"])
            ],
        }
        if not found["pages"]:
            found["note"] = "Nothing matched, try other words"
        return {"success": True, "result": found}
