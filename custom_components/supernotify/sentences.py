"""Voice and chat commands for Home Assistant's built-in conversation agent - beta.

The built-in agent doesn't use an AI model, so it can't use the tools in llm.py. It matches fixed
sentences instead, so Supernotify registers a few of its own, the same way an automation with a
conversation trigger does. English only for now, and switched on in the options.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.core import Context as HAContext
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.trigger import async_initialize_triggers, async_validate_trigger_config
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .model import CommandType, GlobalTargetType, RecipientType
from .schema import EnvelopeOutcome

if TYPE_CHECKING:
    from .engine import SupernotifyEngine

_LOGGER = logging.getLogger(__name__)

EVERYONE = ("everyone", "everybody", "all")
# 15:30, 3:30pm, 3 pm - hours without minutes need am or pm, so a bare number isn't taken as a time
CLOCK_TIME = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?|(\d{1,2}):(\d{2})", re.IGNORECASE)

# hassil sentence templates - (a|b) is a choice, [a] is optional and {slot} is a wildcard.
# A wildcard needs fixed words between it and the next one, so the message is always introduced.
SENTENCES: dict[str, list[str]] = {
    "notify": [
        "(tell|notify|message) {name} (that|saying) {message}",
        "send [a] (message|notification) to {name} (that|saying) {message}",
    ],
    "snooze_minutes": ["(snooze|mute|pause) [all] [my] notifications for [the] [next] {minutes} minutes"],
    "snooze_until": ["(snooze|mute|pause) [all] [my] notifications until {time}"],
    "snooze_hour": ["(snooze|mute|pause) [all] [my] notifications for [an|one] hour"],
    # "mute ... until I say" is left to snooze_until, so it doesn't match both
    "silence": ["(silence|mute) [all] [my] notifications", "silence [all] [my] notifications until I say"],
    "resume": [
        "(unsnooze|unmute|resume) [all] [my] notifications",
        "turn [all] [my] notifications back on",
    ],
    "last": ["what was the last notification", "what notification was sent last"],
}


async def async_register_sentences(hass: HomeAssistant, engine: SupernotifyEngine) -> CALLBACK_TYPE | None:
    """Register the sentences with the built-in conversation agent, returning how to remove them"""

    async def action(run_variables: dict[str, Any], _context: HAContext | None = None) -> ScriptRunResult:
        trigger: dict[str, Any] = run_variables["trigger"]
        response = await async_respond(engine, trigger["id"], trigger.get("slots", {}), _requester(trigger))
        return ScriptRunResult(conversation_response=response, service_response=None, variables={})

    try:
        config = await async_validate_trigger_config(
            hass,
            [{"platform": "conversation", "id": command, "command": sentences} for command, sentences in SENTENCES.items()],
        )
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to register sentences with the built-in conversation agent: %s", e)
        return None
    return await async_initialize_triggers(hass, config, action, DOMAIN, "Supernotify sentences", _log)


def _log(level: int, msg: str, **kwargs: Any) -> None:
    _LOGGER.log(level, "SUPERNOTIFY Sentences: %s", msg, **kwargs)


def _requester(trigger: dict[str, Any]) -> HAContext:
    """The context of the conversation, so notifications and snoozes are linked to who asked"""
    context: dict[str, Any] = (trigger.get("user_input") or {}).get("context") or {}
    return HAContext(user_id=context.get("user_id"), parent_id=context.get("id"))


async def async_respond(engine: SupernotifyEngine, command: str, slots: dict[str, Any], context: HAContext) -> str:
    """Carry out a command, returning what to say back"""
    if command == "notify":
        return await _notify(engine, str(slots.get("name", "")), str(slots.get("message", "")), context)
    if command == "last":
        return _last(engine)
    if command == "snooze_minutes":
        minutes = str(slots.get("minutes", "")).strip().removeprefix("the ").strip().removeprefix("next ").strip()
        if not minutes.isdigit() or int(minutes) < 1:
            return "Say how many minutes as a number, for example snooze notifications for 30 minutes"
        return _snooze(engine, CommandType.SNOOZE, context, dt.timedelta(minutes=int(minutes)))
    if command == "snooze_until":
        spoken = str(slots.get("time", ""))
        if spoken.strip().casefold() == "i say":
            return _snooze(engine, CommandType.SILENCE, context)
        until = _next_time(spoken)
        if until is None:
            return "Say a time like 15:30 or 3:30pm, for example snooze notifications until 15:30"
        return _snooze(engine, CommandType.SNOOZE, context, until - dt_util.now())
    if command == "snooze_hour":
        return _snooze(engine, CommandType.SNOOZE, context, dt.timedelta(hours=1))
    if command == "silence":
        return _snooze(engine, CommandType.SILENCE, context)
    if command == "resume":
        return _snooze(engine, CommandType.NORMAL, context)
    return f"Supernotify doesn't know the command {command}"


async def _notify(engine: SupernotifyEngine, name: str, message: str, context: HAContext) -> str:
    people = engine.context.people_registry
    target: list[str] | None = None
    if name.strip().casefold() not in EVERYONE:
        named = people.people_named(name)
        if len(named) > 1:
            return f"Which {name} do you mean: {' or '.join(sorted(r.alias or r.name for r in named))}?"
        if not named:
            known = ", ".join(sorted(r.alias or r.name for r in people.enabled_recipients())) or "nobody yet"
            return f"I don't know anyone called {name}. I can notify {known}, or everyone"
        target = [named[0].entity_id]
    notification = await engine.async_send_message(message, target=target, context=context)
    if notification is None or not notification.delivered:
        return "Sorry, the notification wasn't sent"
    return "Sent" if target is None else f"Sent to {name}"


def _next_time(spoken: str) -> dt.datetime | None:
    """The next time the clock shows this time, today or tomorrow"""
    match = CLOCK_TIME.fullmatch(spoken.strip())
    if match is None:
        return None
    hour_12, minute_12, meridiem, hour_24, minute_24 = match.groups()
    if meridiem:
        hour = int(hour_12)
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
        minute = int(minute_12 or 0)
    else:
        hour, minute = int(hour_24), int(minute_24)
    if hour > 23 or minute > 59:
        return None
    now = dt_util.as_local(dt_util.now())
    until = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return until if until > now else until + dt.timedelta(days=1)


def _snooze(engine: SupernotifyEngine, cmd: CommandType, context: HAContext, snooze_for: dt.timedelta | None = None) -> str:
    """Snooze, silence or resume everything for the person asking, or for everyone if they aren't known"""
    person_id: str | None = engine.context.people_registry.person_id_for_user_id(context.user_id)
    recipient_type = RecipientType.USER if person_id else RecipientType.EVERYONE
    engine.context.snoozer.register_snooze(
        cmd, GlobalTargetType.EVERYTHING, None, recipient_type, person_id, snooze_for, reason="Voice command"
    )
    whose = "your" if person_id else "all"
    if cmd == CommandType.NORMAL:
        return f"Turned {whose} notifications back on"
    if cmd == CommandType.SILENCE:
        return f"Silenced {whose} notifications until you turn them back on"
    until = dt_util.as_local(dt_util.now() + (snooze_for or engine.context.snoozer.snooze_period))
    return f"Snoozed {whose} notifications until {until.strftime('%H:%M')}"


def _last(engine: SupernotifyEngine) -> str:
    notification = engine.last_notification
    if notification is None:
        return "There haven't been any notifications since Home Assistant started"
    when = dt_util.as_local(notification.created).strftime("%H:%M")
    sent = [name for name, outcomes in notification.deliveries.items() if outcomes.get(EnvelopeOutcome.SUCCESS)]
    if sent:
        return f"At {when}: {notification.message}. Sent by {', '.join(sent)}"
    return f"At {when}: {notification.message}. It wasn't sent by anything"
