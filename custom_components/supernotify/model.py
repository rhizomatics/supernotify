import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntFlag, StrEnum, auto
from typing import Any, ClassVar

import voluptuous as vol

# This import brings in a bunch of other dependency noises, make it manual until py3.14/lazy import/HA updated
# from homeassistant.components.mobile_app import DOMAIN as MOBILE_APP_DOMAIN
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_DEBUG,
    CONF_ENABLED,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import valid_entity_id
from homeassistant.helpers.typing import ConfigType

from . import (
    ATTR_EMAIL,
    ATTR_MOBILE_APP_ID,
    ATTR_PERSON_ID,
    ATTR_PHONE,
    CONF_DATA,
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_DEVICE_MODEL_EXCLUDE,
    CONF_DEVICE_MODEL_INCLUDE,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_SELECTION_RANK,
    CONF_TARGET_REQUIRED,
    CONF_TARGET_USAGE,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    RE_DEVICE_ID,
    SELECTION_DEFAULT,
    TARGET_USE_ON_NO_ACTION_TARGETS,
    SelectionRank,
    phone,
)
from .common import ensure_list

_LOGGER = logging.getLogger(__name__)

# See note on import of homeassistant.components.mobile_app
MOBILE_APP_DOMAIN = "mobile_app"


class TransportFeature(IntFlag):
    MESSAGE = 1
    TITLE = 2
    IMAGES = 4
    VIDEO = 8
    ACTIONS = 16
    TEMPLATE_FILE = 32


class Target:
    # actual targets, that can positively identified with a validator
    DIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_ENTITY_ID, ATTR_DEVICE_ID, ATTR_EMAIL, ATTR_PHONE, ATTR_MOBILE_APP_ID]
    # references that lead to targets, that can positively identified with a validator
    AUTO_INDIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_PERSON_ID]
    # references that lead to targets, that can't be positively identified with a validator
    EXPLICIT_INDIRECT_CATEGORIES: ClassVar[list[str]] = [ATTR_AREA_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID]
    INDIRECT_CATEGORIES = EXPLICIT_INDIRECT_CATEGORIES + AUTO_INDIRECT_CATEGORIES
    AUTO_CATEGORIES = DIRECT_CATEGORIES + AUTO_INDIRECT_CATEGORIES

    CATEGORIES = DIRECT_CATEGORIES + INDIRECT_CATEGORIES

    UNKNOWN_CUSTOM_CATEGORY = "_UNKNOWN_"

    def __init__(
        self,
        target: str
        | list[str]
        | dict[str, str]
        | dict[str, Sequence[str]]
        | dict[str, list[str]]
        | dict[str, str | list[str]]
        | None = None,
        target_data: dict[str, Any] | None = None,
        target_specific_data: bool = False,
    ) -> None:
        self.target_data: dict[str, Any] | None = None
        self.target_specific_data: dict[tuple[str, str], dict[str, Any]] | None = None
        self.targets: dict[str, list[str]] = {}

        matched: list[str]

        if isinstance(target, str):
            target = [target]

        if target is None:
            pass  # empty constructor is valid case for target building
        elif isinstance(target, list):
            # simplified and legacy way of assuming list of entities that can be discriminated by validator
            targets_left = list(target)
            for category in self.AUTO_CATEGORIES:
                validator = getattr(self, f"is_{category}", None)
                if validator is not None:
                    matched = []
                    for t in targets_left:
                        if t not in matched and validator(t):
                            self.targets.setdefault(category, [])
                            self.targets[category].append(t)
                            matched.append(t)
                    targets_left = [t for t in targets_left if t not in matched]
                else:
                    _LOGGER.debug("SUPERNOTIFY Missing validator for selective target category %s", category)
                if not targets_left:
                    break
            if targets_left:
                self.targets[self.UNKNOWN_CUSTOM_CATEGORY] = targets_left

        elif isinstance(target, dict):
            for category in target:
                targets = ensure_list(target[category])
                if not targets:
                    continue
                if category in self.AUTO_CATEGORIES:
                    validator = getattr(self, f"is_{category}", None)
                    if validator is not None:
                        for t in targets:
                            if validator(t):
                                self.targets.setdefault(category, [])
                                if t not in self.targets[category]:
                                    self.targets[category].append(t)
                            else:
                                _LOGGER.warning("SUPERNOTIFY Target skipped invalid %s target: %s", category, t)
                    else:
                        _LOGGER.debug("SUPERNOTIFY Missing validator for selective target category %s", category)

                elif category in self.CATEGORIES:
                    # categories that can't be automatically detected, like label_id
                    self.targets[category] = targets
                else:
                    # custom categories
                    self.targets[category] = targets
        else:
            _LOGGER.warning("SUPERNOTIFY Target created with no valid targets: %s", target)

        if target_data and target_specific_data:
            self.target_specific_data = {}
            for category, targets in self.targets.items():
                for t in targets:
                    self.target_specific_data[category, t] = target_data
        if target_data and not target_specific_data:
            self.target_data = target_data

    # Targets by category

    @property
    def email(self) -> list[str]:
        return self.targets.get(ATTR_EMAIL, [])

    @property
    def entity_ids(self) -> list[str]:
        return self.targets.get(ATTR_ENTITY_ID, [])

    @property
    def person_ids(self) -> list[str]:
        return self.targets.get(ATTR_PERSON_ID, [])

    @property
    def device_ids(self) -> list[str]:
        return self.targets.get(ATTR_DEVICE_ID, [])

    @property
    def phone(self) -> list[str]:
        return self.targets.get(ATTR_PHONE, [])

    @property
    def mobile_app_ids(self) -> list[str]:
        return self.targets.get(ATTR_MOBILE_APP_ID, [])

    def custom_ids(self, category: str) -> list[str]:
        return self.targets.get(category, []) if category not in self.CATEGORIES else []

    @property
    def area_ids(self) -> list[str]:
        return self.targets.get(ATTR_AREA_ID, [])

    @property
    def floor_ids(self) -> list[str]:
        return self.targets.get(ATTR_FLOOR_ID, [])

    @property
    def label_ids(self) -> list[str]:
        return self.targets.get(ATTR_LABEL_ID, [])

    # Selectors / validators

    @classmethod
    def is_device_id(cls, target: str) -> bool:
        return re.fullmatch(RE_DEVICE_ID, target) is not None

    @classmethod
    def is_entity_id(cls, target: str) -> bool:
        return valid_entity_id(target) and not target.startswith("person.")

    @classmethod
    def is_person_id(cls, target: str) -> bool:
        return target.startswith("person.") and valid_entity_id(target)

    @classmethod
    def is_phone(cls, target: str) -> bool:
        try:
            return phone(target) is not None
        except vol.Invalid:
            return False

    @classmethod
    def is_mobile_app_id(cls, target: str) -> bool:
        return not valid_entity_id(target) and target.startswith(f"{MOBILE_APP_DOMAIN}_")

    @classmethod
    def is_email(cls, target: str) -> bool:
        try:
            return vol.Email()(target) is not None  # type: ignore[call-arg]
        except vol.Invalid:
            return False

    def has_targets(self) -> bool:
        return any(targets for category, targets in self.targets.items())

    def has_resolved_target(self) -> bool:
        return any(targets for category, targets in self.targets.items() if category not in self.INDIRECT_CATEGORIES)

    def has_unknown_targets(self) -> bool:
        return len(self.targets.get(self.UNKNOWN_CUSTOM_CATEGORY, [])) > 0

    def for_category(self, category: str) -> list[str]:
        return self.targets.get(category, [])

    def resolved_targets(self) -> list[str]:
        result: list[str] = []
        for category, targets in self.targets.items():
            if category not in self.INDIRECT_CATEGORIES:
                result.extend(targets)
        return result

    def hash_resolved(self) -> int:
        targets = []
        for category in self.targets:
            if category not in self.INDIRECT_CATEGORIES:
                targets.extend(self.targets[category])
        return hash(tuple(targets))

    @property
    def direct_categories(self) -> list[str]:
        return self.DIRECT_CATEGORIES + [cat for cat in self.targets if cat not in self.CATEGORIES]

    def direct(self) -> "Target":
        t = Target(
            {cat: targets for cat, targets in self.targets.items() if cat in self.direct_categories},
            target_data=self.target_data,
        )
        if self.target_specific_data:
            t.target_specific_data = {k: v for k, v in self.target_specific_data.items() if k[0] in self.direct_categories}
        return t

    def extend(self, category: str, targets: list[str] | str) -> None:
        targets = ensure_list(targets)
        self.targets.setdefault(category, [])
        self.targets[category].extend(t for t in targets if t not in self.targets[category])

    def remove(self, category: str, targets: list[str] | str) -> None:
        targets = ensure_list(targets)
        if category in self.targets:
            self.targets[category] = [t for t in self.targets[category] if t not in targets]

    def safe_copy(self) -> "Target":
        t = Target(dict(self.targets), target_data=dict(self.target_data) if self.target_data else None)
        t.target_specific_data = dict(self.target_specific_data) if self.target_specific_data else None
        return t

    def split_by_target_data(self) -> "list[Target]":
        if not self.target_specific_data:
            result = self.safe_copy()
            result.target_specific_data = None
            return [result]
        results: list[Target] = []
        default: Target = self.safe_copy()
        default.target_specific_data = None
        last_found: dict[str, Any] | None = None
        collected: dict[str, list[str]] = {}
        for (category, target), data in self.target_specific_data.items():
            if last_found is None:
                last_found = data
                collected = {category: [target]}
            elif data != last_found and last_found is not None:
                new_target: Target = Target(collected, target_data=last_found)
                results.append(new_target)
                default -= new_target
                last_found = data
                collected = {category: [target]}
            else:
                collected.setdefault(category, [])
                collected[category].append(target)
        new_target = Target(collected, target_data=last_found)
        results.append(new_target)
        default -= new_target
        if default.has_targets():
            results.append(default)
        return results

    def __len__(self) -> int:
        """How many targets, whether direct or indirect"""
        return sum(len(targets) for targets in self.targets.values())

    def __add__(self, other: "Target") -> "Target":
        """Create a new target by adding another to this one"""
        new = Target()
        categories = set(list(self.targets.keys()) + list(other.targets.keys()))
        for category in categories:
            new.targets[category] = list(self.targets.get(category, []))
            new.targets[category].extend(t for t in other.targets.get(category, []) if t not in new.targets[category])

        new.target_data = dict(self.target_data) if self.target_data else None
        if other.target_data:
            if new.target_data is None:
                new.target_data = dict(other.target_data)
            else:
                new.target_data.update(other.target_data)
        new.target_specific_data = dict(self.target_specific_data) if self.target_specific_data else None
        if other.target_specific_data:
            if new.target_specific_data is None:
                new.target_specific_data = dict(other.target_specific_data)
            else:
                new.target_specific_data.update(other.target_specific_data)
        return new

    def __sub__(self, other: "Target") -> "Target":
        """Create a new target by removing another from this one, ignoring target_data"""
        new = Target()
        new.target_data = self.target_data
        if self.target_specific_data:
            new.target_specific_data = {
                k: v for k, v in self.target_specific_data.items() if k[1] not in other.targets.get(k[0], ())
            }
        categories = set(list(self.targets.keys()) + list(other.targets.keys()))
        for category in categories:
            new.targets[category] = []
            new.targets[category].extend(t for t in self.targets.get(category, []) if t not in other.targets.get(category, []))

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
        if self.target_specific_data != other.target_specific_data:
            return False
        return all(self.targets.get(category, []) == other.targets.get(category, []) for category in self.CATEGORIES)

    def as_dict(self, **_kwargs: Any) -> dict[str, list[str]]:
        return {k: v for k, v in self.targets.items() if v}


class TransportConfig:
    def __init__(self, conf: ConfigType | None = None, class_config: "TransportConfig|None" = None) -> None:
        conf = conf or {}
        if class_config is not None:
            self.device_domain: list[str] = conf.get(CONF_DEVICE_DOMAIN, class_config.device_domain)
            if CONF_DEVICE_MODEL_INCLUDE in conf or CONF_DEVICE_MODEL_EXCLUDE in conf:
                # source include and exclude atomically either explicit config or default
                self.device_model_include: list[str] | None = conf.get(CONF_DEVICE_MODEL_INCLUDE)
                self.device_model_exclude: list[str] | None = conf.get(CONF_DEVICE_MODEL_EXCLUDE)
            else:
                self.device_model_include = class_config.device_model_include
                self.device_model_exclude = class_config.device_model_exclude
            self.device_discovery: bool = conf.get(CONF_DEVICE_DISCOVERY, class_config.device_discovery)
            self.enabled: bool = conf.get(CONF_ENABLED, class_config.enabled)
            self.alias = conf.get(CONF_ALIAS)
            self.delivery_defaults: DeliveryConfig = DeliveryConfig(
                conf.get(CONF_DELIVERY_DEFAULTS, {}), class_config.delivery_defaults or None
            )
        else:
            self.device_domain = conf.get(CONF_DEVICE_DOMAIN, [])
            self.device_model_include = conf.get(CONF_DEVICE_MODEL_INCLUDE)
            self.device_model_exclude = conf.get(CONF_DEVICE_MODEL_EXCLUDE)
            self.device_discovery = conf.get(CONF_DEVICE_DISCOVERY, False)
            self.enabled = conf.get(CONF_ENABLED, True)
            self.alias = conf.get(CONF_ALIAS)
            self.delivery_defaults = DeliveryConfig(conf.get(CONF_DELIVERY_DEFAULTS) or {})


class DeliveryCustomization:
    def __init__(self, config: ConfigType | None, target_specific: bool = False) -> None:
        config = config or {}
        self.enabled: bool | None = config.get(CONF_ENABLED, True)  # perhaps should be false for wildcards
        self.data: dict[str, Any] | None = config.get(CONF_DATA)
        self.target: Target | None  # TODO: only works for scenario or recipient, not action call

        if config.get(CONF_TARGET):
            if self.data:
                self.target = Target(config.get(CONF_TARGET), target_data=self.data, target_specific_data=target_specific)
            else:
                self.target = Target(config.get(CONF_TARGET))
        else:
            self.target = None

    def data_value(self, key: str) -> Any:
        return self.data.get(key) if self.data else None

    def as_dict(self, **_kwargs: Any) -> dict[str, Any]:
        return {CONF_TARGET: self.target.as_dict() if self.target else None, CONF_ENABLED: self.enabled, CONF_DATA: self.data}


class DeliveryConfig:
    """Shared config for transport defaults and Delivery definitions"""

    def __init__(self, conf: ConfigType, delivery_defaults: "DeliveryConfig|None" = None) -> None:
        if delivery_defaults is not None:
            # use transport defaults where no delivery level override
            self.target: Target | None = Target(conf.get(CONF_TARGET)) if CONF_TARGET in conf else delivery_defaults.target
            self.target_required: TargetRequired = conf.get(CONF_TARGET_REQUIRED, delivery_defaults.target_required)
            self.target_usage: str = conf.get(CONF_TARGET_USAGE) or delivery_defaults.target_usage
            self.action: str | None = conf.get(CONF_ACTION) or delivery_defaults.action
            self.debug: bool = conf.get(CONF_DEBUG, delivery_defaults.debug)

            self.data: ConfigType = dict(delivery_defaults.data) if isinstance(delivery_defaults.data, dict) else {}
            self.data.update(conf.get(CONF_DATA, {}))
            self.selection: list[str] = conf.get(CONF_SELECTION, delivery_defaults.selection)
            self.priority: list[str] = conf.get(CONF_PRIORITY, delivery_defaults.priority)
            self.selection_rank: SelectionRank = conf.get(CONF_SELECTION_RANK, delivery_defaults.selection_rank)
            self.options: ConfigType = conf.get(CONF_OPTIONS, {})
            # only override options not set in config
            if isinstance(delivery_defaults.options, dict):
                for opt in delivery_defaults.options:
                    self.options.setdefault(opt, delivery_defaults.options[opt])

        else:
            # construct the transport defaults
            self.target = Target(conf.get(CONF_TARGET)) if conf.get(CONF_TARGET) else None
            self.target_required = conf.get(CONF_TARGET_REQUIRED, TargetRequired.ALWAYS)
            self.target_usage = conf.get(CONF_TARGET_USAGE, TARGET_USE_ON_NO_ACTION_TARGETS)
            self.action = conf.get(CONF_ACTION)
            self.debug = conf.get(CONF_DEBUG, False)
            self.options = conf.get(CONF_OPTIONS, {})
            self.data = conf.get(CONF_DATA, {})
            self.selection = conf.get(CONF_SELECTION, [SELECTION_DEFAULT])
            self.priority = conf.get(CONF_PRIORITY, PRIORITY_VALUES)
            self.selection_rank = conf.get(CONF_SELECTION_RANK, SelectionRank.ANY)

    def as_dict(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            CONF_TARGET: self.target.as_dict() if self.target else None,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_DATA: self.data,
            CONF_SELECTION: self.selection,
            CONF_PRIORITY: self.priority,
            CONF_SELECTION_RANK: str(self.selection_rank),
            CONF_TARGET_REQUIRED: str(self.target_required),
            CONF_TARGET_USAGE: self.target_usage,
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
    notification_message: str | None = ""
    notification_title: str | None = ""
    occupancy: list[str] = field(default_factory=list)

    def __init__(
        self,
        applied_scenarios: list[str] | None = None,
        required_scenarios: list[str] | None = None,
        constrain_scenarios: list[str] | None = None,
        delivery_priority: str | None = PRIORITY_MEDIUM,
        occupiers: dict[str, list[Any]] | None = None,
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
        self.notification_message = message
        self.notification_title = title

    def as_dict(self, **_kwargs: Any) -> ConfigType:
        return {
            "applied_scenarios": self.applied_scenarios,
            "required_scenarios": self.required_scenarios,
            "constrain_scenarios": self.constrain_scenarios,
            "notification_message": self.notification_message,
            "notification_title": self.notification_title,
            "notification_priority": self.notification_priority,
            "occupancy": self.occupancy,
        }


class SuppressionReason(StrEnum):
    SNOOZED = "SNOOZED"
    DUPE = "DUPE"
    NO_SCENARIO = "NO_SCENARIO"
    NO_ACTION = "NO_ACTION"
    NO_TARGET = "NO_TARGET"
    TRANSPORT_DISABLED = "TRANSPORT_DISABLED"
    PRIORITY = "PRIORITY"
    DELIVERY_CONDITION = "DELIVERY_CONDITION"
    UNKNOWN = "UNKNOWN"


class TargetRequired(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    OPTIONAL = auto()

    @classmethod
    def _missing_(cls, value: Any) -> "TargetRequired|None":
        """Backward compatibility for binary values"""
        if value is True or (isinstance(value, str) and value.lower() in ("true", "on")):
            return cls.ALWAYS
        if value is False or (isinstance(value, str) and value.lower() in ("false", "off")):
            return cls.OPTIONAL
        return None


class TargetType(StrEnum):
    pass


class GlobalTargetType(TargetType):
    NONCRITICAL = "NONCRITICAL"
    EVERYTHING = "EVERYTHING"


class RecipientType(StrEnum):
    USER = "USER"
    EVERYONE = "EVERYONE"


class QualifiedTargetType(TargetType):
    TRANSPORT = "TRANSPORT"
    DELIVERY = "DELIVERY"
    CAMERA = "CAMERA"
    PRIORITY = "PRIORITY"
    MOBILE = "MOBILE"


class CommandType(StrEnum):
    SNOOZE = "SNOOZE"
    SILENCE = "SILENCE"
    NORMAL = "NORMAL"


class MessageOnlyPolicy(StrEnum):
    STANDARD = "STANDARD"  # independent title and message
    USE_TITLE = "USE_TITLE"  # use title in place of message, no title
    # use combined title and message as message, no title
    COMBINE_TITLE = "COMBINE_TITLE"


class DebugTrace:
    def __init__(
        self,
        message: str | None,
        title: str | None,
        data: dict[str, Any] | None,
        target: dict[str, list[str]] | list[str] | str | None,
    ) -> None:
        self.message: str | None = message
        self.title: str | None = title
        self.data: dict[str, Any] | None = dict(data) if data else data
        self.target: dict[str, list[str]] | list[str] | str | None = list(target) if target else target
        self.resolved: dict[str, dict[str, Any]] = {}
        self.delivery_selection: dict[str, list[str]] = {}
        self.delivery_artefacts: dict[str, Any] = {}
        self._last_stage: dict[str, str] = {}

    def contents(self, **_kwargs: Any) -> dict[str, Any]:
        results: dict[str, Any] = {
            "message": self.message,
            "title": self.title,
            "data": self.data,
            "target": self.target,
            "resolved": self.resolved,
            "delivery_selection": self.delivery_selection,
        }
        if self.delivery_artefacts:
            results["delivery_artefacts"] = self.delivery_artefacts
        return results

    def record_target(self, delivery_name: str, stage: str, computed: Target | list[Target]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        self.resolved.setdefault(delivery_name, {})
        self.resolved[delivery_name].setdefault(stage, {})
        if isinstance(computed, Target):
            combined = computed
        else:
            combined = Target()
            for target in ensure_list(computed):
                combined += target
        result: str | dict[str, Any] = combined.as_dict()
        if self._last_stage.get(delivery_name):
            last_target = self.resolved[delivery_name][self._last_stage[delivery_name]]
            if last_target is not None and last_target == result:
                result = "NO_CHANGE"

        self.resolved[delivery_name][stage] = result
        self._last_stage[delivery_name] = stage

    def record_delivery_selection(self, stage: str, delivery_selection: list[str]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        self.delivery_selection[stage] = delivery_selection

    def record_delivery_artefact(self, delivery: str, artefact_name: str, artefact: Any) -> None:
        self.delivery_artefacts.setdefault(delivery, {})
        self.delivery_artefacts[delivery][artefact_name] = artefact
