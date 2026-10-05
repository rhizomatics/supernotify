"""Voice and chat commands for Home Assistant's built-in conversation agent - beta.

The built-in agent doesn't use an AI model, so it can't use the tools in llm.py. It matches fixed
sentences instead, so Supernotify registers a few of its own, the same way an automation with a
conversation trigger does. English and Italian for now, and switched on in the options.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.core import Context as HAContext
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.trigger import async_initialize_triggers, async_validate_trigger_config
from homeassistant.util import dt as dt_util

from . import DOMAIN
from .model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType, TargetType
from .schema import EnvelopeOutcome

if TYPE_CHECKING:
    from .engine import SupernotifyEngine
    from .notification import Notification

_LOGGER = logging.getLogger(__name__)


class Subject(NamedTuple):
    """The camera or tag a voice snooze is for, and how it was said"""

    target_type: QualifiedTargetType
    target: str
    spoken: str


EVERYONE = ("everyone", "everybody", "all", "tutti", "tutte")
DEFAULT_LANGUAGE = "en"
# 3:30pm, 3 pm, 12 a.m.
MERIDIEM_TIME = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?", re.IGNORECASE)
# 15:30, 15.30, 1530, 3:30 or a bare hour like 3
CLOCK_TIME = re.compile(r"(\d{1,2})(?:[:.]?(\d{2}))?")
# "half three" isn't taken, since some places mean 2:30 by it
HALF_PAST = re.compile(r"half past (\w+)", re.IGNORECASE)
HOURS_SAID = {
    word: hour
    for hour, word in enumerate(
        ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"], start=1
    )
} | {str(hour): hour for hour in range(1, 13)}
NAMED_TIMES = {"midnight": 0, "noon": 12}
# Optional words before the minutes, which the wildcard can take in with the number
MINUTES_PREFIXES = ("the", "next", "i", "prossimi")
# A tag starting or ending with this names a camera, as "driveway camera" or "telecamera vialetto"
CAMERA_WORDS = {"en": "camera", "it": "telecamera"}

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
        # the tag sentence comes first, since the agent takes the first that matches, and the minutes
        # wildcard in the other would otherwise take in "driveway for 20"
        "snooze_minutes": [
            "(snooze|mute|pause) [all] [my] notifications for {tag} for [the] [next] {minutes} minutes",
            "(snooze|mute|pause) [all] [my] notifications for [the] [next] {minutes} minutes",
        ],
        "snooze_until": [
            "(snooze|mute|pause) [all] [my] notifications until {time}",
            "(snooze|mute|pause) [all] [my] notifications for {tag} until {time}",
        ],
        "snooze_hour": [
            "(snooze|mute|pause) [all] [my] notifications for [an|one] hour",
            "(snooze|mute|pause) [all] [my] notifications for {tag} for [an|one] hour",
        ],
        # "mute ... until I say" is left to snooze_until, so it doesn't match both
        "silence": ["(silence|mute) [all] [my] notifications", "silence [all] [my] notifications until I say"],
        "resume": [
            "(unsnooze|unmute|resume) [all] [my] notifications",
            "turn [all] [my] notifications back on",
            "(unsnooze|unmute|resume) [all] [my] notifications for {tag}",
            "turn [all] [my] notifications for {tag} back on",
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
            "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche per [i] [prossimi] {minutes} minuti",
            (
                "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche "
                "(di|del|della|dello|dei|delle) {tag} per [i] [prossimi] {minutes} minuti"
            ),
        ],
        "snooze_until": [
            "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche fino alle {time}",
            (
                "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche "
                "(di|del|della|dello|dei|delle) {tag} fino alle {time}"
            ),
        ],
        "snooze_hour": [
            "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche per (un'ora|un ora|una ora)",
            (
                "(posticipa|sospendi|silenzia|metti in pausa) [tutte] [le] [mie] notifiche "
                "(di|del|della|dello|dei|delle) {tag} per (un'ora|un ora|una ora)"
            ),
        ],
        "silence": ["(silenzia|zittisci|disattiva) [tutte] [le] [mie] notifiche [finché non lo dico|fino a nuovo ordine]"],
        "resume": [
            "(riattiva|ripristina|riprendi) [tutte] [le] [mie] notifiche",
            "(riaccendi|rimetti) [tutte] [le] [mie] notifiche",
            "(riattiva|ripristina|riprendi) [tutte] [le] [mie] notifiche (di|del|della|dello|dei|delle) {tag}",
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
        "resumed_yours": "Turned your notifications{about} back on",
        "resumed_all": "Turned all notifications{about} back on",
        "silenced_yours": "Silenced your notifications{about} until you turn them back on",
        "silenced_all": "Silenced all notifications{about} until you turn them back on",
        "snoozed_yours": "Snoozed your notifications{about} until {until}",
        "snoozed_all": "Snoozed all notifications{about} until {until}",
        "about": " for {tag}",
        "unknown_tag": "I can't find a scenario or entity called {tag}, so nothing was changed",
        "which_camera": "{tag} could be {cameras}. Say which one",
        "no_last": "There haven't been any notifications since Home Assistant started",
        "last_sent": "At {when}: {message}. Sent via {sent}",
        "last_not_sent": "At {when}: {message}. It wasn't sent{why}",
        "why_no_delivery": " because nothing is set up to send it",
        "why_error": " because of an error",
        "why_snoozed": " because notifications were snoozed or silenced",
        "why_dupe": " because it was a duplicate",
        "why_no_scenario": " because a scenario it needs wasn't active",
        "why_priority": " because of its priority",
        "why_delivery_condition": " because its conditions weren't met",
        "why_occupancy": " because of who was home",
        "why_transport_disabled": " because the transport is switched off",
        "why_no_target": " because there was nobody to send it to",
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
        "resumed_yours": "Ho riattivato le tue notifiche{about}",
        "resumed_all": "Ho riattivato tutte le notifiche{about}",
        "silenced_yours": "Ho silenziato le tue notifiche{about} finché non le riattivi",
        "silenced_all": "Ho silenziato tutte le notifiche{about} finché non le riattivi",
        "snoozed_yours": "Ho posticipato le tue notifiche{about} fino alle {until}",
        "snoozed_all": "Ho posticipato tutte le notifiche{about} fino alle {until}",
        "about": " di {tag}",
        "unknown_tag": "Non trovo nessuno scenario o entità chiamato {tag}, quindi non ho cambiato niente",
        "which_camera": "{tag} può essere {cameras}. Dimmi quale",
        "no_last": "Non ci sono state notifiche da quando Home Assistant si è avviato",
        "last_sent": "Alle {when}: {message}. Inviata tramite {sent}",
        "last_not_sent": "Alle {when}: {message}. Non è stata inviata{why}",
        "why_no_delivery": " perché niente è configurato per inviarla",
        "why_error": " a causa di un errore",
        "why_snoozed": " perché le notifiche erano posticipate o silenziate",
        "why_dupe": " perché era un duplicato",
        "why_no_scenario": " perché uno scenario richiesto non era attivo",
        "why_priority": " per via della sua priorità",
        "why_delivery_condition": " perché le sue condizioni non erano soddisfatte",
        "why_occupancy": " per via di chi era in casa",
        "why_transport_disabled": " perché il transport è disattivato",
        "why_no_target": " perché non c'era nessuno a cui inviarla",
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
    tag: str | None = _tag(str(slots["tag"])) if slots.get("tag") else None
    subject: Subject | None = None
    if tag is not None:
        subject_or_reply: Subject | str = _subject(engine, tag, command, language)
        if isinstance(subject_or_reply, str):
            return subject_or_reply
        subject = subject_or_reply
    if command == "snooze_minutes":
        minutes = _minutes(str(slots.get("minutes", "")))
        if not minutes.isdigit() or int(minutes) < 1:
            return _say(language, "minutes_as_number")
        return _snooze(engine, CommandType.SNOOZE, context, language, dt.timedelta(minutes=int(minutes)), subject)
    if command == "snooze_until":
        spoken = str(slots.get("time", ""))
        if spoken.strip().casefold() == "i say":
            return _snooze(engine, CommandType.SILENCE, context, language, subject=subject)
        until = _next_time(spoken, language)
        if until is None:
            return _say(language, "time_as_clock")
        return _snooze(engine, CommandType.SNOOZE, context, language, until - dt_util.now(), subject)
    if command == "snooze_hour":
        return _snooze(engine, CommandType.SNOOZE, context, language, dt.timedelta(hours=1), subject)
    if command == "silence":
        return _snooze(engine, CommandType.SILENCE, context, language)
    if command == "resume":
        return _snooze(engine, CommandType.NORMAL, context, language, subject=subject)
    return _say(language, "unknown_command", command=command)


def _subject(engine: SupernotifyEngine, tag: str, command: str, language: str) -> Subject | str:
    """A camera snooze when the tag names one camera, otherwise a tag snooze - or what to say back
    when it names several cameras, or nothing at all"""
    words: list[str] = tag.split()
    camera_word: str = CAMERA_WORDS.get(language, CAMERA_WORDS[DEFAULT_LANGUAGE])
    if len(words) > 1 and camera_word in (words[0].casefold(), words[-1].casefold()):
        name: str = " ".join(words[1:] if words[0].casefold() == camera_word else words[:-1])
        hass_api = engine.context.hass_api
        cameras: list[str] = sorted({
            e for e in hass_api.entity_ids_named(name) + hass_api.entity_ids_named(tag) if e.startswith("camera.")
        })
        if len(cameras) > 1:
            return _say(language, "which_camera", tag=tag, cameras=_say(language, "or").join(cameras))
        if cameras:
            return Subject(QualifiedTargetType.CAMERA, cameras[0], tag)
    if command != "resume" and not engine.tag_matches(tag):
        return _say(language, "unknown_tag", tag=tag)
    return Subject(QualifiedTargetType.TAG, tag, tag)


def _tag(spoken: str) -> str:
    """The tag, without a leading 'the' the wildcard took in"""
    words: list[str] = spoken.split()
    if len(words) > 1 and words[0].casefold() == "the":
        words.pop(0)
    return " ".join(words)


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
    """The next time the clock shows this time, today or tomorrow

    In English, 3:30 without am or pm is whichever 3:30 comes next, while 03:30 is always the morning.
    Italian uses the 24 hour clock, so 3:30 is always the morning there.
    """
    spoken = spoken.strip()
    either_half_of_day = False
    if (match := MERIDIEM_TIME.fullmatch(spoken)) is not None:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if match.group(3).lower() == "p" else 0)
    elif (match := CLOCK_TIME.fullmatch(spoken)) is not None:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        either_half_of_day = language != "it" and not match.group(1).startswith("0")
    elif language != "it" and (match := HALF_PAST.fullmatch(spoken)) is not None:
        if match.group(1).casefold() not in HOURS_SAID:
            return None
        hour, minute, either_half_of_day = HOURS_SAID[match.group(1).casefold()], 30, True
    elif spoken.casefold() in NAMED_TIMES:
        hour, minute = NAMED_TIMES[spoken.casefold()], 0
    else:
        return None
    if hour > 23 or minute > 59:
        return None
    hours = [hour % 12, hour % 12 + 12] if either_half_of_day and 1 <= hour <= 12 else [hour]
    now = dt_util.as_local(dt_util.now())
    return min(_next_occurrence(now, candidate, minute) for candidate in hours)


def _next_occurrence(now: dt.datetime, hour: int, minute: int) -> dt.datetime:
    until = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return until if until > now else until + dt.timedelta(days=1)


def _snooze(
    engine: SupernotifyEngine,
    cmd: CommandType,
    context: HAContext,
    language: str,
    snooze_for: dt.timedelta | None = None,
    subject: Subject | None = None,
) -> str:
    """Snooze, silence or resume everything, or a camera or tag, for the person asking, or for everyone
    if they aren't known"""
    person_id: str | None = engine.context.people_registry.person_id_for_user_id(context.user_id)
    recipient_type = RecipientType.USER if person_id else RecipientType.EVERYONE
    # "silence" said at bedtime with nothing named still lets critical alerts through - nobody saying it
    # means the smoke alarm too. Resuming clears both kinds, so a snooze of everything can still be undone.
    target_type: TargetType = subject.target_type if subject else GlobalTargetType.NONCRITICAL
    engine.context.snoozer.register_snooze(
        cmd, target_type, subject.target if subject else None, recipient_type, person_id, snooze_for, reason="Voice command"
    )
    if cmd == CommandType.NORMAL and not subject:
        engine.context.snoozer.register_snooze(cmd, GlobalTargetType.EVERYTHING, None, recipient_type, person_id, None)
    whose = "yours" if person_id else "all"
    about: str = ""
    if subject:
        matches: list[str] = (
            [subject.target] if subject.target_type == QualifiedTargetType.CAMERA else engine.tag_matches(subject.target)
        )
        about = _say(language, "about", tag=subject.spoken) + (f" ({', '.join(matches)})" if matches else "")
    if cmd == CommandType.NORMAL:
        return _say(language, f"resumed_{whose}", about=about)
    if cmd == CommandType.SILENCE:
        return _say(language, f"silenced_{whose}", about=about)
    until = dt_util.as_local(dt_util.now() + (snooze_for or engine.context.snoozer.snooze_period))
    return _say(language, f"snoozed_{whose}", about=about, until=_clock(until, language))


def _clock(when: dt.datetime, language: str) -> str:
    """A time to say back, with am or pm in English so a wrong guess at the half of the day can be put right"""
    if language == "it":
        return when.strftime("%H:%M")
    return f"{when.hour % 12 or 12}:{when.minute:02d}{'am' if when.hour < 12 else 'pm'}"


def _last(engine: SupernotifyEngine, language: str) -> str:
    notification = engine.last_notification
    if notification is None:
        return _say(language, "no_last")
    when = dt_util.as_local(notification.created).strftime("%H:%M")
    sent = [name for name, outcomes in notification.deliveries.items() if outcomes.get(EnvelopeOutcome.SUCCESS)]
    if sent:
        return _say(language, "last_sent", when=when, message=notification.message, sent=", ".join(sent))
    return _say(language, "last_not_sent", when=when, message=notification.message, why=_why_not_sent(notification, language))


def _why_not_sent(notification: Notification, language: str) -> str:
    """Why nothing was sent, or nothing to add when there's no plain way to say it"""
    if notification.failed:
        return _say(language, "why_error")
    if not notification.deliveries and not notification._skip_reasons:
        return _say(language, "why_no_delivery")
    for reason in notification._skip_reasons:
        key: str = f"why_{reason.lower()}"
        if key in RESPONSES[DEFAULT_LANGUAGE]:
            return _say(language, key)
    return ""
