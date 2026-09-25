"""Voice and chat commands for Home Assistant's built-in conversation agent - beta.

The built-in agent doesn't use an AI model, so it can't use the tools in llm.py. It matches fixed
sentences instead, so Supernotify registers a few of its own, the same way an automation with a
conversation trigger does. English and Italian for now, and switched on in the options.
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

EVERYONE = ("everyone", "everybody", "all", "tutti", "tutte")
DEFAULT_LANGUAGE = "en"
# 15:30, 3:30pm, 3 pm - hours without minutes need am or pm, so a bare number isn't taken as a time
CLOCK_TIME = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?|(\d{1,2}):(\d{2})", re.IGNORECASE)
# Italian uses the 24 hour clock, so a bare hour is a time - 15, 15:30 or 15.30
CLOCK_TIME_24H = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?")
# Optional words before the minutes, which the wildcard can take in with the number
MINUTES_PREFIXES = ("the", "next", "i", "prossimi")

# hassil sentence templates by language - (a|b) is a choice, [a] is optional and {slot} is a wildcard.
# A wildcard needs fixed words between it and the next one, so the message is always introduced.
# Every language is registered, since the built-in agent matches trigger sentences whatever the
# language of the assistant, and the answer is given in the language of the sentence that matched.
SENTENCES: dict[str, dict[str, list[str]]] = {
    "en": {
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
    },
    "it": {
        "notify": [
            "(avvisa|avverti|informa) {name} che {message}",
            "(di|dì|di'|dici|scrivi) a {name} che {message}",
            "(manda|invia) (un messaggio|una notifica) a {name} (che dice|dicendo|con scritto|che) {message}",
        ],
        "snooze_minutes": [
            "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche per [i] [prossimi] {minutes} minuti"
        ],
        "snooze_until": ["(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche fino alle {time}"],
        "snooze_hour": [
            "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche per (un'ora|un ora|una ora)"
        ],
        "silence": ["(silenzia|zittisci|disattiva) [tutte] [le] [mie] notifiche [finché non lo dico|fino a nuovo ordine]"],
        "resume": [
            "(riattiva|ripristina|riprendi) [tutte] [le] [mie] notifiche",
            "(riaccendi|rimetti) [tutte] [le] [mie] notifiche",
        ],
        "last": [
            "(qual è|qual era|quale è|quale era) [stata] (l'ultima|l ultima) notifica",
            "(dimmi|leggi|ripeti) (l'ultima|l ultima) notifica",
        ],
    },
}

# What to say back, by the language of the sentence that matched
RESPONSES: dict[str, dict[str, str]] = {
    "en": {
        "sent": "Sent",
        "sent_to": "Sent to {name}",
        "not_sent": "Sorry, the notification wasn't sent",
        "which": "Which {name} do you mean: {choices}?",
        "or": " or ",
        "unknown_name": "I don't know anyone called {name}. I can notify {known}, or everyone",
        "nobody_yet": "nobody yet",
        "minutes_as_number": "Say how many minutes as a number, for example snooze notifications for 30 minutes",
        "time_as_clock": "Say a time like 15:30 or 3:30pm, for example snooze notifications until 15:30",
        "resumed_yours": "Turned your notifications back on",
        "resumed_all": "Turned all notifications back on",
        "silenced_yours": "Silenced your notifications until you turn them back on",
        "silenced_all": "Silenced all notifications until you turn them back on",
        "snoozed_yours": "Snoozed your notifications until {until}",
        "snoozed_all": "Snoozed all notifications until {until}",
        "no_last": "There haven't been any notifications since Home Assistant started",
        "last_sent": "At {when}: {message}. Sent by {sent}",
        "last_not_sent": "At {when}: {message}. It wasn't sent by anything",
        "unknown_command": "Supernotify doesn't know the command {command}",
    },
    "it": {
        "sent": "Inviata",
        "sent_to": "Inviata a {name}",
        "not_sent": "Mi dispiace, la notifica non è stata inviata",
        "which": "Quale {name} intendi: {choices}?",
        "or": " o ",
        "unknown_name": "Non conosco nessuno che si chiama {name}. Posso avvisare {known}, oppure tutti",
        "nobody_yet": "ancora nessuno",
        "minutes_as_number": "Dimmi i minuti con un numero, per esempio posticipa le notifiche per 30 minuti",
        "time_as_clock": "Dimmi un orario come 15 o 15:30, per esempio posticipa le notifiche fino alle 15:30",
        "resumed_yours": "Ho riattivato le tue notifiche",
        "resumed_all": "Ho riattivato tutte le notifiche",
        "silenced_yours": "Ho silenziato le tue notifiche finché non le riattivi",
        "silenced_all": "Ho silenziato tutte le notifiche finché non le riattivi",
        "snoozed_yours": "Ho posticipato le tue notifiche fino alle {until}",
        "snoozed_all": "Ho posticipato tutte le notifiche fino alle {until}",
        "no_last": "Non ci sono state notifiche da quando Home Assistant si è avviato",
        "last_sent": "Alle {when}: {message}. Inviata da {sent}",
        "last_not_sent": "Alle {when}: {message}. Non è stata inviata da nessun canale",
        "unknown_command": "Supernotify non conosce il comando {command}",
    },
}


def _say(language: str, key: str, **values: Any) -> str:
    """A response in the given language, or in English if there's none"""
    return RESPONSES.get(language, RESPONSES[DEFAULT_LANGUAGE])[key].format(**values)


async def async_register_sentences(hass: HomeAssistant, engine: SupernotifyEngine) -> CALLBACK_TYPE | None:
    """Register the sentences with the built-in conversation agent, returning how to remove them"""

    async def action(run_variables: dict[str, Any], _context: HAContext | None = None) -> ScriptRunResult:
        trigger: dict[str, Any] = run_variables["trigger"]
        language, _, command = str(trigger["id"]).rpartition(".")
        response = await async_respond(
            engine, command, trigger.get("slots", {}), _requester(trigger), language or DEFAULT_LANGUAGE
        )
        return ScriptRunResult(conversation_response=response, service_response=None, variables={})

    try:
        config = await async_validate_trigger_config(
            hass,
            [
                {"platform": "conversation", "id": f"{language}.{command}", "command": sentences}
                for language, commands in SENTENCES.items()
                for command, sentences in commands.items()
            ],
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


async def async_respond(
    engine: SupernotifyEngine, command: str, slots: dict[str, Any], context: HAContext, language: str = DEFAULT_LANGUAGE
) -> str:
    """Carry out a command, returning what to say back in the language of the sentence"""
    if command == "notify":
        return await _notify(engine, str(slots.get("name", "")), str(slots.get("message", "")), context, language)
    if command == "last":
        return _last(engine, language)
    if command == "snooze_minutes":
        minutes = _minutes(str(slots.get("minutes", "")))
        if not minutes.isdigit() or int(minutes) < 1:
            return _say(language, "minutes_as_number")
        return _snooze(engine, CommandType.SNOOZE, context, language, dt.timedelta(minutes=int(minutes)))
    if command == "snooze_until":
        spoken = str(slots.get("time", ""))
        if spoken.strip().casefold() == "i say":
            return _snooze(engine, CommandType.SILENCE, context, language)
        until = _next_time(spoken, language)
        if until is None:
            return _say(language, "time_as_clock")
        return _snooze(engine, CommandType.SNOOZE, context, language, until - dt_util.now())
    if command == "snooze_hour":
        return _snooze(engine, CommandType.SNOOZE, context, language, dt.timedelta(hours=1))
    if command == "silence":
        return _snooze(engine, CommandType.SILENCE, context, language)
    if command == "resume":
        return _snooze(engine, CommandType.NORMAL, context, language)
    return _say(language, "unknown_command", command=command)


def _minutes(spoken: str) -> str:
    """The number of minutes, without optional words the wildcard took in, like 'the next' or 'i prossimi'"""
    words: list[str] = spoken.split()
    while words and words[0].casefold() in MINUTES_PREFIXES:
        words.pop(0)
    return " ".join(words)


async def _notify(engine: SupernotifyEngine, name: str, message: str, context: HAContext, language: str) -> str:
    people = engine.context.people_registry
    target: list[str] | None = None
    if name.strip().casefold() not in EVERYONE:
        named = people.people_named(name)
        if len(named) > 1:
            choices = _say(language, "or").join(sorted(r.alias or r.name for r in named))
            return _say(language, "which", name=name, choices=choices)
        if not named:
            known = ", ".join(sorted(r.alias or r.name for r in people.enabled_recipients())) or _say(language, "nobody_yet")
            return _say(language, "unknown_name", name=name, known=known)
        target = [named[0].entity_id]
    notification = await engine.async_send_message(message, target=target, context=context)
    if notification is None or not notification.delivered:
        return _say(language, "not_sent")
    return _say(language, "sent") if target is None else _say(language, "sent_to", name=name)


def _next_time(spoken: str, language: str = DEFAULT_LANGUAGE) -> dt.datetime | None:
    """The next time the clock shows this time, today or tomorrow"""
    match = CLOCK_TIME.fullmatch(spoken.strip())
    if match is not None:
        hour_12, minute_12, meridiem, hour_24, minute_24 = match.groups()
        if meridiem:
            hour = int(hour_12)
            if not 1 <= hour <= 12:
                return None
            hour = hour % 12 + (12 if meridiem.lower() == "p" else 0)
            minute = int(minute_12 or 0)
        else:
            hour, minute = int(hour_24), int(minute_24)
    elif language == "it" and (match := CLOCK_TIME_24H.fullmatch(spoken.strip())) is not None:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    now = dt_util.as_local(dt_util.now())
    until = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return until if until > now else until + dt.timedelta(days=1)


def _snooze(
    engine: SupernotifyEngine, cmd: CommandType, context: HAContext, language: str, snooze_for: dt.timedelta | None = None
) -> str:
    """Snooze, silence or resume everything for the person asking, or for everyone if they aren't known"""
    person_id: str | None = engine.context.people_registry.person_id_for_user_id(context.user_id)
    recipient_type = RecipientType.USER if person_id else RecipientType.EVERYONE
    engine.context.snoozer.register_snooze(
        cmd, GlobalTargetType.EVERYTHING, None, recipient_type, person_id, snooze_for, reason="Voice command"
    )
    whose = "yours" if person_id else "all"
    if cmd == CommandType.NORMAL:
        return _say(language, f"resumed_{whose}")
    if cmd == CommandType.SILENCE:
        return _say(language, f"silenced_{whose}")
    until = dt_util.as_local(dt_util.now() + (snooze_for or engine.context.snoozer.snooze_period))
    return _say(language, f"snoozed_{whose}", until=until.strftime("%H:%M"))


def _last(engine: SupernotifyEngine, language: str) -> str:
    notification = engine.last_notification
    if notification is None:
        return _say(language, "no_last")
    when = dt_util.as_local(notification.created).strftime("%H:%M")
    sent = [name for name, outcomes in notification.deliveries.items() if outcomes.get(EnvelopeOutcome.SUCCESS)]
    if sent:
        return _say(language, "last_sent", when=when, message=notification.message, sent=", ".join(sent))
    return _say(language, "last_not_sent", when=when, message=notification.message)
