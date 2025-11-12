import logging
import time
from typing import Any

from homeassistant.core import Event

from . import (
    ATTR_ACTION,
    ATTR_MOBILE_APP_ID,
    ATTR_PERSON_ID,
    ATTR_USER_ID,
    CONF_PERSON,
    PRIORITY_CRITICAL,
    PRIORITY_MEDIUM,
)
from .common import format_timestamp
from .delivery import Delivery
from .model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType, Target, TargetType
from .people import PeopleRegistry

SNOOZE_TIME = 60 * 60  # TODO: move to configuration
_LOGGER = logging.getLogger(__name__)


class Snooze:
    target: str | list[str] | None
    target_type: TargetType
    snoozed_at: float
    snooze_until: float | None = None
    recipient_type: RecipientType
    recipient: str | None
    reason: str | None = None

    def __init__(
        self,
        target_type: TargetType,
        recipient_type: RecipientType,
        target: str | list[str] | None = None,
        recipient: str | None = None,
        snooze_for: int | None = None,
        reason: str | None = None,
    ) -> None:
        self.snoozed_at = time.time()
        self.target = target
        self.target_type = target_type
        self.recipient_type = recipient_type
        self.recipient = recipient
        self.reason = reason
        if snooze_for:
            self.snooze_until = self.snoozed_at + snooze_for

    def std_recipient(self) -> str | None:
        return self.recipient if self.recipient_type == RecipientType.USER else RecipientType.EVERYONE

    def short_key(self) -> str:
        #  only one GLOBAL can be active at a time
        target = "GLOBAL" if self.target_type in GlobalTargetType else f"{self.target_type}_{self.target}"
        return f"{target}_{self.std_recipient()}"

    def __eq__(self, other: object) -> bool:
        """Check if two snoozes for the same thing"""
        if not isinstance(other, Snooze):
            return False
        return self.short_key() == other.short_key()

    def __repr__(self) -> str:
        """Return a string representation of the object."""
        return f"Snooze({self.target_type}, {self.target}, {self.std_recipient()})"

    def active(self) -> bool:
        return self.snooze_until is None or self.snooze_until > time.time()

    def export(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "target": self.target,
            "recipient_type": self.recipient_type,
            "recipient": self.recipient,
            "reason": self.reason,
            "snoozed_at": format_timestamp(self.snoozed_at),
            "snooze_until": format_timestamp(self.snooze_until),
        }


class Snoozer:
    """Manage snoozing"""

    def __init__(self, people_registry: PeopleRegistry | None = None) -> None:
        self.snoozes: dict[str, Snooze] = {}
        self.people_registry: PeopleRegistry | None = people_registry

    def handle_command_event(self, event: Event, people: dict[str, Any] | None = None) -> None:
        people = people or {}
        try:
            cmd: CommandType
            target_type: TargetType | None = None
            target: str | None = None
            snooze_for: int = SNOOZE_TIME
            recipient_type: RecipientType | None = None
            event_name = event.data.get(ATTR_ACTION)

            if not event_name:
                _LOGGER.warning(
                    "SUPERNOTIFY Invalid Mobile Action: %s, %s, %s, %s",
                    event.origin,
                    event.time_fired,
                    event.data,
                    event.context,
                )
                return

            _LOGGER.debug(
                "SUPERNOTIFY Mobile Action: %s, %s, %s, %s", event.origin, event.time_fired, event.data, event.context
            )
            event_parts: list[str] = event_name.split("_")
            if len(event_parts) < 4:
                _LOGGER.warning("SUPERNOTIFY Malformed mobile event action %s", event_name)
                return
            cmd = CommandType[event_parts[1]]
            recipient_type = RecipientType[event_parts[2]]
            if event_parts[3] in QualifiedTargetType and len(event_parts) > 4:
                target_type = QualifiedTargetType[event_parts[3]]
                target = event_parts[4]
                snooze_for = int(event_parts[-1]) if len(event_parts) == 6 else SNOOZE_TIME
            elif event_parts[3] in GlobalTargetType and len(event_parts) >= 4:
                target_type = GlobalTargetType[event_parts[3]]
                snooze_for = int(event_parts[-1]) if len(event_parts) == 5 else SNOOZE_TIME

            if cmd is None or target_type is None or recipient_type is None:
                _LOGGER.warning("SUPERNOTIFY Invalid mobile event name %s", event_name)
                return

        except KeyError as ke:
            _LOGGER.warning("SUPERNOTIFY Unknown enum in event %s: %s", event, ke)
            return
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to analyze event %s: %s", event, e)
            return

        try:
            recipient: str | None = None
            if recipient_type == RecipientType.USER:
                target_people = [
                    p.get(CONF_PERSON)
                    for p in people.values()
                    if p.get(ATTR_USER_ID) == event.context.user_id and event.context.user_id is not None and p.get(CONF_PERSON)
                ]
                if target_people:
                    recipient = target_people[0]
                    _LOGGER.debug("SUPERNOTIFY mobile action from %s mapped to %s", event.context.user_id, recipient)
                else:
                    _LOGGER.warning("SUPERNOTIFY Unable to find person for action from %s", event.context.user_id)
                    return

            self.register_snooze(cmd, target_type, target, recipient_type, recipient, snooze_for)

        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to handle event %s: %s", event, e)

    def register_snooze(
        self,
        cmd: CommandType,
        target_type: TargetType,
        target: str | None,
        recipient_type: RecipientType,
        recipient: str | None,
        snooze_for: int | None,
        reason: str = "User command",
    ) -> None:
        if cmd == CommandType.SNOOZE:
            snooze = Snooze(target_type, recipient_type, target, recipient, snooze_for, reason=reason)
            self.snoozes[snooze.short_key()] = snooze
        elif cmd == CommandType.SILENCE:
            snooze = Snooze(target_type, recipient_type, target, recipient, reason=reason)
            self.snoozes[snooze.short_key()] = snooze
        elif cmd == CommandType.NORMAL:
            anti_snooze = Snooze(target_type, recipient_type, target, recipient)
            to_del = [k for k, v in self.snoozes.items() if v.short_key() == anti_snooze.short_key()]
            for k in to_del:
                del self.snoozes[k]
        else:
            _LOGGER.warning(  # type: ignore
                "SUPERNOTIFY Invalid mobile cmd %s (target_type: %s, target: %s, recipient_type: %s)",
                cmd,
                target_type,
                target,
                recipient_type,
            )

    def purge_snoozes(self) -> None:
        to_del = [k for k, v in self.snoozes.items() if not v.active()]
        for k in to_del:
            del self.snoozes[k]

    def clear(self) -> int:
        cleared = len(self.snoozes)
        self.snoozes.clear()
        return cleared

    def export(self) -> list[dict[str, Any]]:
        return [s.export() for s in self.snoozes.values()]

    def current_snoozes(
        self,
        priority: str = PRIORITY_MEDIUM,
        delivery_names: list[str] | None = None,
        delivery_definitions: dict[str, Delivery] | None = None,
    ) -> list[Snooze]:
        delivery_names = delivery_names or []
        delivery_definitions = delivery_definitions or {}
        inscope_snoozes: list[Snooze] = []

        for snooze in self.snoozes.values():
            if snooze.active():
                match snooze.target_type:
                    case GlobalTargetType.EVERYTHING:
                        inscope_snoozes.append(snooze)
                    case GlobalTargetType.NONCRITICAL:
                        if priority != PRIORITY_CRITICAL:
                            inscope_snoozes.append(snooze)
                    case QualifiedTargetType.DELIVERY:
                        if snooze.target in delivery_names:
                            inscope_snoozes.append(snooze)
                    case QualifiedTargetType.PRIORITY:
                        if snooze.target == priority:
                            inscope_snoozes.append(snooze)
                    case QualifiedTargetType.MOBILE:
                        inscope_snoozes.append(snooze)
                    case QualifiedTargetType.TRANSPORT:
                        if snooze.target in [delivery_definitions[d].transport.name for d in delivery_names]:
                            inscope_snoozes.append(snooze)
                    case QualifiedTargetType.CAMERA:
                        inscope_snoozes.append(snooze)
                    case _:
                        _LOGGER.warning("SUPERNOTIFY Unhandled target type %s", snooze.target_type)

        return inscope_snoozes

    def is_global_snooze(self, priority: str = PRIORITY_MEDIUM) -> bool:
        for snooze in self.snoozes.values():
            if snooze.active():
                match snooze.target_type:
                    case GlobalTargetType.EVERYTHING:
                        return True
                    case GlobalTargetType.NONCRITICAL:
                        if priority != PRIORITY_CRITICAL:
                            return True

        return False

    def filter_recipients(
        self,
        recipients: Target,
        priority: str,
        delivery_name: str,
        transport: "Transport",  # type: ignore  # noqa: F821
        all_delivery_names: list[str],
        delivery_definitions: dict[str, Delivery],
    ) -> Target:
        inscope_snoozes = self.current_snoozes(priority, all_delivery_names, delivery_definitions)
        for snooze in inscope_snoozes:
            if snooze.recipient_type == RecipientType.USER:
                # assume the everyone checks are made before notification gets this far
                if (
                    (snooze.target_type == QualifiedTargetType.DELIVERY and snooze.target == delivery_name)
                    or (snooze.target_type == QualifiedTargetType.TRANSPORT and snooze.target == transport.name)
                    or (
                        snooze.target_type == QualifiedTargetType.PRIORITY
                        and (snooze.target == priority or (isinstance(snooze.target, list) and priority in snooze.target))
                    )
                    or snooze.target_type == GlobalTargetType.EVERYTHING
                    or (snooze.target_type == GlobalTargetType.NONCRITICAL and priority != PRIORITY_CRITICAL)
                ):
                    recipients_to_remove = []
                    for recipient in recipients.person_ids:
                        if recipient == snooze.recipient:
                            recipients_to_remove.append(recipient)
                            _LOGGER.info("SUPERNOTIFY Snoozing %s", snooze.recipient)

                    recipients.remove(ATTR_PERSON_ID, recipients_to_remove)

                if snooze.target_type == QualifiedTargetType.MOBILE:
                    to_remove: list[str] = []
                    for recipient in recipients.mobile_app_ids:
                        if recipient == snooze.target:
                            _LOGGER.debug("SUPERNOTIFY Snoozing %s for %s", snooze.recipient, snooze.target)
                            to_remove.append(recipient)
                    if to_remove:
                        recipients.remove(ATTR_MOBILE_APP_ID, to_remove)
        return recipients
