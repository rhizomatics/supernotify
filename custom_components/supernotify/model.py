import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar, cast

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_ENABLED,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import valid_entity_id
from homeassistant.helpers.typing import ConfigType

from . import (
    ATTR_ACTION,
    ATTR_EMAIL,
    ATTR_OTHER_ID,
    ATTR_PERSON_ID,
    ATTR_PHONE,
    CONF_DATA,
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_TARGET_REQUIRED,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
)
from .common import ensure_list


class Target:
    DIRECT_CATEGORIES: ClassVar[dict[str, str]] = {
        ATTR_ENTITY_ID: "entity_ids",
        ATTR_DEVICE_ID: "device_ids",
        ATTR_EMAIL: "email",
        ATTR_PHONE: "phone",
        ATTR_OTHER_ID: "other_ids",
        ATTR_ACTION: "actions",
    }
    INDIRECT_CATEGORIES: ClassVar[dict[str, str]] = {
        ATTR_PERSON_ID: "person_ids",
        ATTR_AREA_ID: "area_ids",
        ATTR_FLOOR_ID: "floor_ids",
        ATTR_LABEL_ID: "label_ids",
    }
    CATEGORIES = DIRECT_CATEGORIES | INDIRECT_CATEGORIES

    def __init__(
        self, target: str | list[str] | dict[str, str | list[str]] | None = None, target_data: dict[str, Any] | None = None
    ) -> None:
        # core home assistant direct target types
        self.device_ids: list[str] = []
        self.entity_ids: list[str] = []
        # core home assistant indirect target selector types
        self.area_ids: list[str] = []
        self.floor_ids: list[str] = []
        self.label_ids: list[str] = []
        # other target types
        self.email: list[str] = []
        self.phone: list[str] = []
        self.other_ids: list[str] = []
        self.actions: list[str] = []
        # other target selector types
        self.person_ids: list[str] = []

        # target specific action data
        self.target_data = target_data

        # once resolved, indirect selectors removed
        self.resolved = False

        if isinstance(target, list):
            # simplified and legacy way of assuming list of entities
            for t in target:
                if self.is_entity_id(t):
                    self.entity_ids.append(t)
                elif self.is_device_id(t):
                    self.device_ids.append(t)
                elif self.is_email(t):
                    self.email.append(t)
                elif self.is_phone(t):
                    self.phone.append(t)
                elif self.is_person_id(t):
                    self.person_ids.append(t)
                else:
                    self.other_ids.append(t)
        elif isinstance(target, str):
            self.entity_ids = [target] if not self.is_device_id(target) else []
            self.device_ids = [target] if self.is_device_id(target) else []
            self.email = [target] if self.is_email(target) else []
            self.person_ids = [target] if self.is_person_id(target) else []
            self.phone = [target] if self.is_phone(target) else []
        elif target is None:
            self.entity_ids = []
        elif isinstance(target, dict):
            for category, attr in self.CATEGORIES.items():
                setattr(self, attr, ensure_list(target.get(category)))
            for k in [cat for cat in target if cat not in self.CATEGORIES]:
                self.other_ids.extend(ensure_list(target.get(k)))
            self.email = [a for a in self.email if self.is_email(a)]
            self.phone = [a for a in self.phone if self.is_phone(a)]
            self.entity_ids = [a for a in self.entity_ids if self.is_entity_id(a)]
            self.device_ids = [a for a in self.device_ids if self.is_device_id(a)]
            self.person_ids = [a for a in self.person_ids if self.is_person_id(a)]

    @classmethod
    def is_device_id(cls, target: str) -> bool:
        return re.match(r"^[0-9a-f]{32}$", target) is not None

    @classmethod
    def is_entity_id(cls, target: str) -> bool:
        return valid_entity_id(target) and not target.startswith("person.")

    @classmethod
    def is_person_id(cls, target: str) -> bool:
        return valid_entity_id(target) and target.startswith("person.")

    @classmethod
    def is_email(cls, target: str) -> bool:
        return (
            re.fullmatch(
                r"^[a-zA-Z0-9.+/=?^_-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$",
                target,
            )
            is not None
        )

    def has_resolved_target(self) -> bool:
        return any((self.entity_ids, self.device_ids, self.other_ids, self.email, self.phone, self.actions))

    @classmethod
    def is_phone(cls, target: str) -> bool:
        return re.fullmatch(r"^(\+\d{1,3})?\s?\(?\d{1,4}\)?[\s.-]?\d{3}[\s.-]?\d{4}$", target) is not None

    def for_category(self, category: str) -> list[str]:
        if category in self.CATEGORIES:
            return cast("list[str]", getattr(self, self.CATEGORIES[category]))
        return []

    def direct(self) -> "Target":
        t = Target(target_data=self.target_data)
        for attr in self.DIRECT_CATEGORIES.values():
            setattr(t, attr, getattr(self, attr))
        return t

    def __add__(self, other: "Target") -> "Target":
        """Create a new target by adding another to this one"""
        new = Target()
        for category in self.CATEGORIES:
            new.extend(category, self.for_category(category))
            new.extend(category, other.for_category(category))
        new.target_data = dict(self.target_data) if self.target_data else None
        if other.target_data:
            if new.target_data is None:
                new.target_data = dict(other.target_data)
            else:
                new.target_data.update(other.target_data)
        return new

    def __eq__(self, other: object) -> bool:
        """Compare two targets"""
        if other is self:
            return True
        if other is None:
            return False
        if not isinstance(other, Target):
            return NotImplemented
        if self.target_data != other.target_data:
            return False
        return all(self.for_category(category) == other.for_category(category) for category in self.CATEGORIES)

    def extend(self, category: str, targets: list[str] | str) -> None:
        if category in self.CATEGORIES:
            attr = getattr(self, self.CATEGORIES[category])
            attr.extend([t for t in ensure_list(targets) if t not in attr])

    def remove(self, category: str, targets: list[str] | str) -> None:
        if category in self.CATEGORIES:
            attr = getattr(self, self.CATEGORIES[category])
            for t in targets:
                if t in attr:
                    attr.remove(t)

    def as_dict(self) -> dict[str, list[str]]:
        d = {}
        for category, attr_name in self.CATEGORIES.items():
            attr = getattr(self, attr_name)
            if attr:
                d[category] = attr
        return d


class MethodConfig:
    def __init__(self, name: str, conf: ConfigType) -> None:
        self.name = name
        self.target_required: bool | None = conf.get(CONF_TARGET_REQUIRED)
        self.device_domain = conf.get(CONF_DEVICE_DOMAIN, [])
        self.device_discovery: bool | None = conf.get(CONF_DEVICE_DISCOVERY)
        self.enabled = conf.get(CONF_ENABLED, True)
        self.delivery_defaults = DeliveryConfig(conf.get(CONF_DELIVERY_DEFAULTS) or {})


class DeliveryConfig:
    """Shared config for method defaults and Delivery definitions"""

    def __init__(self, conf: ConfigType, delivery_defaults: "DeliveryConfig|None" = None) -> None:
        if delivery_defaults is not None:
            # use method defaults where no delivery level override
            self.target: Target | None = Target(conf.get(CONF_TARGET)) if CONF_TARGET in conf else delivery_defaults.target
            self.action: str | None = conf.get(CONF_ACTION) or delivery_defaults.action
            self.options: ConfigType = dict(delivery_defaults.options)
            self.options.update(conf.get(CONF_OPTIONS, {}))
            self.data: ConfigType = dict(delivery_defaults.data) or {}
            self.data.update(conf.get(CONF_DATA, {}))
            self.selection: list[str] = conf.get(CONF_SELECTION, delivery_defaults.selection)
            self.priority: list[str] = conf.get(CONF_PRIORITY, delivery_defaults.priority)
        else:
            # construct the method defaults
            self.target = Target(conf.get(CONF_TARGET)) if conf.get(CONF_TARGET) else None
            self.action = conf.get(CONF_ACTION)
            self.options = conf.get(CONF_OPTIONS, {})
            self.data = conf.get(CONF_DATA, {})
            self.selection = conf.get(CONF_SELECTION, [SELECTION_DEFAULT])
            self.priority = conf.get(CONF_PRIORITY, PRIORITY_VALUES)

    def apply_method_options(self, method_options: dict[str, Any]) -> None:
        method_options = method_options or {}
        for opt in method_options:
            if opt not in self.options:
                self.options[opt] = method_options[opt]

    def as_dict(self) -> dict[str, Any]:
        return {
            CONF_TARGET: self.target.as_dict() if self.target else None,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_DATA: self.data,
            CONF_SELECTION: self.selection,
            CONF_PRIORITY: self.priority,
        }

    def __repr__(self) -> str:
        """Log friendly representation"""
        return str(self.as_dict())


@dataclass
class ConditionVariables:
    """Variables presented to all condition evaluations

    Attributes
    ----------
        applied_scenarios (list[str]): Scenarios that have been applied
        required_scenarios (list[str]): Scenarios that must be applied
        constrain_scenarios (list[str]): Only scenarios in this list, or in explicit apply_scenarios, can be applied
        notification_priority (str): Priority of the notification
        notification_message (str): Message of the notification
        notification_title (str): Title of the notification
        occupancy (list[str]): List of occupancy scenarios

    """

    applied_scenarios: list[str] = field(default_factory=list)
    required_scenarios: list[str] = field(default_factory=list)
    constrain_scenarios: list[str] = field(default_factory=list)
    notification_priority: str = PRIORITY_MEDIUM
    notification_message: str = ""
    notification_title: str = ""
    occupancy: list[str] = field(default_factory=list)

    def __init__(
        self,
        applied_scenarios: list[str] | None = None,
        required_scenarios: list[str] | None = None,
        constrain_scenarios: list[str] | None = None,
        delivery_priority: str | None = PRIORITY_MEDIUM,
        occupiers: dict[str, list[dict[str, Any]]] | None = None,
        message: str | None = None,
        title: str | None = None,
    ) -> None:
        occupiers = occupiers or {}
        self.occupancy = []
        if not occupiers.get(STATE_NOT_HOME) and occupiers.get(STATE_HOME):
            self.occupancy.append("ALL_HOME")
        elif occupiers.get(STATE_NOT_HOME) and not occupiers.get(STATE_HOME):
            self.occupancy.append("ALL_AWAY")
        if len(occupiers.get(STATE_HOME, [])) == 1:
            self.occupancy.extend(["LONE_HOME", "SOME_HOME"])
        elif len(occupiers.get(STATE_HOME, [])) > 1 and occupiers.get(STATE_NOT_HOME):
            self.occupancy.extend(["MULTI_HOME", "SOME_HOME"])
        self.applied_scenarios = applied_scenarios or []
        self.required_scenarios = required_scenarios or []
        self.constrain_scenarios = constrain_scenarios or []
        self.notification_priority = delivery_priority or PRIORITY_MEDIUM
        self.notification_message = message or ""
        self.notification_title = title or ""

    def as_dict(self) -> ConfigType:
        return {
            "applied_scenarios": self.applied_scenarios,
            "required_scenarios": self.required_scenarios,
            "constrain_scenarios": self.constrain_scenarios,
            "notification_message": self.notification_message,
            "notification_title": self.notification_title,
            "occupancy": self.occupancy,
        }


class SuppressionReason(StrEnum):
    SNOOZED = "SNOOZED"
    DUPE = "DUPE"
    NO_SCENARIO = "NO_SCENARIO"


class TargetType(StrEnum):
    pass


class GlobalTargetType(TargetType):
    NONCRITICAL = "NONCRITICAL"
    EVERYTHING = "EVERYTHING"


class RecipientType(StrEnum):
    USER = "USER"
    EVERYONE = "EVERYONE"


class QualifiedTargetType(TargetType):
    METHOD = "METHOD"
    DELIVERY = "DELIVERY"
    CAMERA = "CAMERA"
    PRIORITY = "PRIORITY"
    ACTION = "ACTION"


class CommandType(StrEnum):
    SNOOZE = "SNOOZE"
    SILENCE = "SILENCE"
    NORMAL = "NORMAL"


class MessageOnlyPolicy(StrEnum):
    STANDARD = "STANDARD"  # independent title and message
    USE_TITLE = "USE_TITLE"  # use title in place of message, no title
    COMBINE_TITLE = "COMBINE_TITLE"  # use combined title and message as message, no title
