from __future__ import annotations

import abc
import logging
import re
from dataclasses import dataclass, field
from enum import IntFlag, StrEnum, auto
from traceback import format_exception
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITIONS,
    CONF_DEBUG,
    CONF_ENABLED,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import (
    Context as HAContext,
)

from .common import ensure_list
from .const import (
    CONF_DATA,
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_DEVICE_MODEL_EXCLUDE,
    CONF_DEVICE_MODEL_INCLUDE,
    CONF_INCLUSION,
    CONF_MESSAGE,
    CONF_OCCUPANCY,
    CONF_PRIORITY,
    CONF_SELECTION_RANK,
    CONF_TARGET_REQUIRED,
    CONF_TARGET_USAGE,
    CONF_TEMPLATE,
    CONF_TITLE,
    INCLUSION_DEFAULT,
    OCCUPANCY_ALL,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    TARGET_USE_ON_NO_ACTION_TARGETS,
)
from .schema import SelectionRank
from .target import Target

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.helpers.typing import ConfigType, TemplateVarsType

_LOGGER = logging.getLogger(__name__)


class TransportFeature(IntFlag):
    MESSAGE = 1
    TITLE = 2
    IMAGES = 4
    VIDEO = 8
    ACTIONS = 16
    TEMPLATE_FILE = 32
    SNAPSHOT_IMAGE = 64  # transports will be deferred if a camera PTZ is defined
    SPOKEN = 128
    SOUND = 256  # sirens, chimes, buzzers, all non-spoken audio


class TransportConfig:
    def __init__(self, conf: ConfigType | None = None, class_config: TransportConfig | None = None) -> None:
        # local import: options.py imports SelectionRule from this module, so importing
        # its constants back at module level here would be circular
        from .options import (
            OPTION_DEVICE_DISCOVERY,
            OPTION_DEVICE_DOMAIN,
            OPTION_DEVICE_MODEL_SELECT,
            SELECT_EXCLUDE,
            SELECT_INCLUDE,
        )

        conf = conf or {}
        if class_config is not None:
            self.enabled: bool = conf.get(CONF_ENABLED, class_config.enabled)
            self.alias = conf.get(CONF_ALIAS)
            self.delivery_defaults: DeliveryConfig = DeliveryConfig(
                conf.get(CONF_DELIVERY_DEFAULTS, {}), class_config.delivery_defaults or None
            )
        else:
            self.enabled = conf.get(CONF_ENABLED, True)
            self.alias = conf.get(CONF_ALIAS)
            self.delivery_defaults = DeliveryConfig(conf.get(CONF_DELIVERY_DEFAULTS) or {})

        # deprecation support
        device_domain = conf.get(CONF_DEVICE_DOMAIN)
        if device_domain is not None:
            _LOGGER.warning("SUPERNOTIFY device_domain on transport deprecated, use options instead")
            self.delivery_defaults.options[OPTION_DEVICE_DOMAIN] = device_domain
        device_model_include = conf.get(CONF_DEVICE_MODEL_INCLUDE)
        device_model_exclude = conf.get(CONF_DEVICE_MODEL_EXCLUDE)
        if device_model_include is not None or device_model_exclude is not None:
            _LOGGER.warning("SUPERNOTIFY device_model_include/exclude on transport deprecated, use options instead")
            self.delivery_defaults.options[OPTION_DEVICE_MODEL_SELECT] = {
                SELECT_INCLUDE: device_model_include,
                SELECT_EXCLUDE: device_model_exclude,
            }
        device_discovery = conf.get(CONF_DEVICE_DISCOVERY)
        if device_discovery is not None and self.delivery_defaults.options.get(OPTION_DEVICE_DISCOVERY) is None:
            _LOGGER.warning("SUPERNOTIFY device_discovery on transport deprecated, use options instead")
            self.delivery_defaults.options[OPTION_DEVICE_DISCOVERY] = device_discovery


class DeliveryCustomization:
    def __init__(
        self, config: ConfigType | None = None, target_specific: bool = False, default_enabled: bool | None = None
    ) -> None:
        config = config or {}
        # defining a customization doesn't imply that the delivery is always enabled -
        # default_enabled only fills in when the `enabled` key is omitted entirely (dict.get
        # default only applies when the key is absent), never overrides an explicit
        # `enabled: None`/`false`/`true` - e.g. Scenario.enabling_deliveries() relies on this to
        # treat a directly-named delivery with no `enabled` key as enabling it (matching the
        # list/string delivery config forms), but not one explicitly set to `enabled: None`
        # just to carry other data (e.g. a priority override).
        self.enabled: bool | None = config.get(CONF_ENABLED, default_enabled)
        self.data: dict[str, Any] | None = config.get(CONF_DATA)
        # TODO: only works for scenario or recipient, not action call
        self.target: Target | None

        if config.get(CONF_TARGET):
            if self.data:
                self.target = Target(config.get(CONF_TARGET), target_data=self.data, target_specific_data=target_specific)
            else:
                self.target = Target(config.get(CONF_TARGET))
        else:
            self.target = None

    def data_value(self, key: str) -> Any:  # ruff: ignore[any-type]
        return self.data.get(key) if self.data else None

    def as_dict(self, **_kwargs: Any) -> dict[str, Any]:
        return {CONF_TARGET: self.target.as_dict() if self.target else None, CONF_ENABLED: self.enabled, CONF_DATA: self.data}


class SelectionRule:
    def __init__(self, config: str | list[str] | dict | SelectionRule | None) -> None:
        # local import: see TransportConfig.__init__ for why this can't be module-level
        from .options import SELECT_EXCLUDE, SELECT_INCLUDE

        self.include: list[str] | None = None
        self.exclude: list[str] | None = None
        if config is None:
            return
        if isinstance(config, SelectionRule):
            self.include = config.include
            self.exclude = config.exclude
        elif isinstance(config, str):
            self.include = [config]
        elif isinstance(config, list):
            self.include = config
        else:
            if config.get(SELECT_INCLUDE):
                self.include = ensure_list(config.get(SELECT_INCLUDE))
            if config.get(SELECT_EXCLUDE):
                self.exclude = ensure_list(config.get(SELECT_EXCLUDE))

    def match(self, v: str | Iterable[str] | None) -> bool:
        if self.include is None and self.exclude is None:
            return True
        if isinstance(v, str) or v is None:
            if self.exclude is not None and v is not None and any(re.fullmatch(pat, v) for pat in self.exclude):
                return False
            if self.include is not None and (v is None or not any(re.fullmatch(pat, v) for pat in self.include)):
                return False
        else:
            if self.exclude is not None:
                for vv in v:
                    if any(re.fullmatch(pat, vv) for pat in self.exclude):
                        return False
            if self.include is not None:
                return any(any(re.fullmatch(pat, vv) for pat in self.include) for vv in v)
        return True


class DataFilter:
    r"""Accepts a dict structure and returns a filtered copy, with arbitrary-depth key filtering.

    Config format (same structure applies recursively at each level):
      str | list   -- shorthand: include only keys matching these patterns
      dict:
        include: list[str]  -- include only keys matching these patterns
        exclude: list[str]  -- exclude keys matching these patterns
        exclude: dict       -- exclude tree: null value = exclude that key,
                               dict value = keep key but apply tree recursively to its value
        <key>: sub-config   -- any other key: sub-filter applied to that key's dict value

    Patterns are matched with re.fullmatch. Sub-filter key lookup is exact (not regex).
    include and exclude can be combined; any non-reserved key adds a sub-filter.
    """

    def __init__(self, config: str | list[str] | dict | None) -> None:
        self._include: list[str] | None = None
        self._exclude: list[str] | None = None
        self._sub: dict[str, DataFilter] = {}
        if config is None:
            return
        if isinstance(config, str):
            self._include = [config]
        elif isinstance(config, list):
            self._include = config
        else:
            self._init_from_dict(config)

    def _init_from_dict(self, config: dict) -> None:
        # local import: see TransportConfig.__init__ for why this can't be module-level
        from .options import SELECT_EXCLUDE, SELECT_INCLUDE

        include_val = config.get(SELECT_INCLUDE)
        exclude_val = config.get(SELECT_EXCLUDE)
        if isinstance(include_val, dict):
            # include as dict: keys = include patterns, non-null values = sub-filters
            self._include = list(include_val.keys())
            for k, v in include_val.items():
                if v is not None:
                    self._sub[k] = DataFilter(v)
        elif include_val is not None:
            self._include = ensure_list(include_val)
        if isinstance(exclude_val, dict):
            excludes, subs = DataFilter._parse_exclude_tree(exclude_val)
            self._exclude = excludes or None
            self._sub.update(subs)
        elif exclude_val is not None:
            self._exclude = ensure_list(exclude_val)
        for k, v in config.items():
            if k in (SELECT_INCLUDE, SELECT_EXCLUDE) or k in self._sub:
                continue
            if isinstance(v, dict) and (SELECT_INCLUDE in v or SELECT_EXCLUDE in v):
                # value is an explicit DataFilter config (has reserved keys) → sub-filter only, all keys pass
                self._sub[k] = DataFilter(v)
            else:
                # null or value without reserved keys → include pattern (+ sub-filter if non-null)
                if self._include is None:
                    self._include = []
                self._include.append(k)
                if v is not None:
                    self._sub[k] = DataFilter(v)

    @staticmethod
    def _parse_exclude_tree(tree: dict) -> tuple[list[str], dict[str, DataFilter]]:
        excludes: list[str] = []
        subs: dict[str, DataFilter] = {}
        for k, v in tree.items():
            if v is None:
                excludes.append(k)
            else:
                subs[k] = DataFilter._exclude_tree_to_filter(v)
        return excludes, subs

    @staticmethod
    def _exclude_tree_to_filter(tree: dict) -> DataFilter:
        df = DataFilter(None)
        excludes, subs = DataFilter._parse_exclude_tree(tree)
        df._exclude = excludes or None
        df._sub = subs
        return df

    def _match(self, key: str) -> bool:
        if self._exclude is None and self._include is None:
            return True
        if self._exclude is not None and any(re.fullmatch(p, key) for p in self._exclude):
            return False
        return self._include is None or any(re.fullmatch(p, key) for p in self._include)

    def apply(self, data: dict[str, Any], *, prune_empty: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in data.items():
            if not self._match(key):
                _LOGGER.debug("SUPERNOTIFY Pruning %s:%s", key, value)
                continue
            if key in self._sub and isinstance(value, dict):
                value = self._sub[key].apply(value, prune_empty=prune_empty)
            if prune_empty and value == {}:
                _LOGGER.debug("SUPERNOTIFY Pruning empty %s", key)
                continue
            result[key] = value
        return result


class DeliveryConfig:
    """Shared config for transport defaults and Delivery definitions"""

    def __init__(self, conf: ConfigType, delivery_defaults: DeliveryConfig | None = None) -> None:

        if delivery_defaults is not None:
            # use transport defaults where no delivery level override
            self.target: Target | None = Target(conf.get(CONF_TARGET)) if CONF_TARGET in conf else delivery_defaults.target
            self.target_required: TargetRequired = conf.get(CONF_TARGET_REQUIRED, delivery_defaults.target_required)
            self.target_usage: str = conf.get(CONF_TARGET_USAGE) or delivery_defaults.target_usage
            self.action: str | None = conf.get(CONF_ACTION) or delivery_defaults.action
            self.debug: bool = conf.get(CONF_DEBUG, delivery_defaults.debug)

            self.data: ConfigType = dict(delivery_defaults.data) if isinstance(delivery_defaults.data, dict) else {}
            self.data.update(conf.get(CONF_DATA, {}))
            self.inclusion: list[str] = conf.get(CONF_INCLUSION, delivery_defaults.inclusion)
            self.priority: list[str] = conf.get(CONF_PRIORITY, delivery_defaults.priority)
            self.selection_rank: SelectionRank = conf.get(CONF_SELECTION_RANK, delivery_defaults.selection_rank)
            self.options: ConfigType = conf.get(CONF_OPTIONS, {})
            # only override options not set in config
            if isinstance(delivery_defaults.options, dict):
                for opt in delivery_defaults.options:
                    self.options.setdefault(opt, delivery_defaults.options[opt])
            self.alias: str | None = conf.get(CONF_ALIAS, delivery_defaults.alias)
            self.template: str | None = conf.get(CONF_TEMPLATE, delivery_defaults.template)
            self.message: str | None = conf.get(CONF_MESSAGE, delivery_defaults.message)
            self.title: str | None = conf.get(CONF_TITLE, delivery_defaults.title)
            self.occupancy: str = conf.get(CONF_OCCUPANCY, delivery_defaults.occupancy)
            self.conditions_config: list[ConfigType] | None = conf.get(CONF_CONDITIONS, delivery_defaults.conditions_config)
        else:
            # construct the transport defaults
            self.target = Target(conf.get(CONF_TARGET)) if conf.get(CONF_TARGET) else None
            self.target_required = conf.get(CONF_TARGET_REQUIRED, TargetRequired.ALWAYS)
            self.target_usage = conf.get(CONF_TARGET_USAGE, TARGET_USE_ON_NO_ACTION_TARGETS)
            self.action = conf.get(CONF_ACTION)
            self.debug = conf.get(CONF_DEBUG, False)
            self.options = conf.get(CONF_OPTIONS, {})
            self.data = conf.get(CONF_DATA, {})
            self.inclusion = conf.get(CONF_INCLUSION, [INCLUSION_DEFAULT])
            self.priority = conf.get(CONF_PRIORITY, list(PRIORITY_VALUES.keys()))
            self.selection_rank = conf.get(CONF_SELECTION_RANK, SelectionRank.ANY)
            self.alias = conf.get(CONF_ALIAS)
            self.template = conf.get(CONF_TEMPLATE)
            self.message = conf.get(CONF_MESSAGE)
            self.title = conf.get(CONF_TITLE)
            self.occupancy = conf.get(CONF_OCCUPANCY, OCCUPANCY_ALL)
            self.conditions_config = conf.get(CONF_CONDITIONS)

    def as_dict(self, **_kwargs: Any) -> dict[str, Any]:
        return {
            CONF_TARGET: self.target.as_dict() if self.target else None,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_DATA: self.data,
            CONF_INCLUSION: self.inclusion,
            CONF_PRIORITY: self.priority,
            CONF_SELECTION_RANK: str(self.selection_rank),
            CONF_TARGET_REQUIRED: str(self.target_required),
            CONF_TARGET_USAGE: self.target_usage,
            CONF_ALIAS: self.alias,
            CONF_TEMPLATE: self.template,
            CONF_MESSAGE: self.message,
            CONF_TITLE: self.title,
            CONF_OCCUPANCY: self.occupancy,
            CONF_CONDITIONS: self.conditions_config,
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
        notification_data (dict[str,Any]): Additional data passed on notify action call

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
        notification_data: dict[str, Any] | None = None,
    ) -> None:
        occupiers = occupiers or {}
        self.occupancy = []
        if not occupiers.get(STATE_NOT_HOME) and not occupiers.get(STATE_HOME):
            self.occupancy.append("UNDEFINED_OCCUPANTS")
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
        self.notification_data: dict[str, Any] = notification_data or {}

    def as_dict(self, **_kwargs: Any) -> TemplateVarsType:
        return {
            "applied_scenarios": self.applied_scenarios,
            "required_scenarios": self.required_scenarios,
            "constrain_scenarios": self.constrain_scenarios,
            "notification_message": self.notification_message,
            "notification_title": self.notification_title,
            "notification_priority": self.notification_priority,
            "occupancy": self.occupancy,
            "notification_data": self.notification_data,
        }


class SuppressionReason(StrEnum):
    SNOOZED = "SNOOZED"
    DUPE = "DUPE"
    NO_SCENARIO = "NO_SCENARIO"
    NO_ACTION = "NO_ACTION"
    NO_TARGET = "NO_TARGET"
    INVALID_ACTION_DATA = "INVALID_ACTION_DATA"
    TRANSPORT_DISABLED = "TRANSPORT_DISABLED"
    PRIORITY = "PRIORITY"
    DELIVERY_CONDITION = "DELIVERY_CONDITION"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"


class TargetRequired(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    OPTIONAL = auto()

    @classmethod
    def _missing_(cls, value: Any) -> TargetRequired | None:  # ruff: ignore[any-type]
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
        debug: bool = True,
    ) -> None:
        self.debug: bool = debug
        self.message: str | None = message
        self.title: str | None = title
        self.data: dict[str, Any] | None = dict(data) if data else data
        self.target: dict[str, list[str]] | list[str] | str | None = list(target) if target else target
        self.resolved: dict[str, dict[str, Any]] = {}
        self.delivery_selection: dict[str, list[str]] = {}
        self.delivery_provenance: dict[str, dict[str, list[str]]] = {}
        self.delivery_artefacts: dict[str, Any] = {}
        self.delivery_exceptions: dict[str, dict[str, list[list[str]]]] = {}
        self._last_stage: dict[str, str] = {}
        self._last_target: dict[str, Any] = {}

    def contents(self, **_kwargs: Any) -> dict[str, Any]:
        results: dict[str, Any] = {
            "arguments": {
                "message": self.message,
                "title": self.title,
                "data": self.data,
                "target": self.target,
            },
            "delivery_selection": self.delivery_selection,
            "resolved": self.resolved,
        }
        if self.delivery_artefacts:
            results["delivery_artefacts"] = self.delivery_artefacts
        if self.delivery_exceptions:
            results["delivery_exceptions"] = self.delivery_exceptions
        return results

    def record_target(self, delivery_name: str, stage: str, computed: Target | list[Target]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        if not self.debug:
            return
        self.resolved.setdefault(delivery_name, {})
        self.resolved[delivery_name].setdefault(stage, {})
        self._last_target.setdefault(delivery_name, {})
        self._last_target[delivery_name].setdefault(stage, {})
        if isinstance(computed, Target):
            combined = computed
        else:
            combined = Target()
            for target in ensure_list(computed):
                combined += target
        new_target: dict[str, Any] = combined.as_dict()
        result: str | dict[str, Any] = new_target
        if self._last_stage.get(delivery_name):
            last_target = self._last_target[delivery_name][self._last_stage[delivery_name]]
            if last_target is not None and last_target == result:
                result = "NO_CHANGE"

        self.resolved[delivery_name][stage] = result
        self._last_stage[delivery_name] = stage
        self._last_target[delivery_name][stage] = new_target

    def record_delivery_selection(self, stage: str, delivery_selection: list[str]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        if not self.debug:
            return
        self.delivery_selection[stage] = delivery_selection

    def record_delivery_provenance(self, delivery: str, effect: str, source: str) -> None:
        """Record which source switched a delivery on or off, where `record_delivery_selection`
        only has the combined list per stage.

        `effect` is `enabled_by` or `disabled_by`, `source` is `default`, `call`,
        `scenario:<name>` or `recipient:<name>`.

        Unlike the rest of the trace this is recorded without `debug`, since it is small - a few
        names per delivery - and archived with every notification, as its `delivery_provenance`.
        """
        sources = self.delivery_provenance.setdefault(delivery, {}).setdefault(effect, [])
        if source not in sources:
            sources.append(source)

    def record_delivery_artefact(self, delivery: str, artefact_name: str, artefact: Any) -> None:  # ruff: ignore[any-type]
        if not self.debug:
            return
        self.delivery_artefacts.setdefault(delivery, {})
        self.delivery_artefacts[delivery][artefact_name] = artefact

    def record_delivery_exception(self, delivery: str, context: str, exception: Exception) -> None:
        if not self.debug:
            return
        self.delivery_exceptions.setdefault(delivery, {})
        self.delivery_exceptions[delivery].setdefault(context, [])
        self.delivery_exceptions[delivery][context].append(format_exception(exception))


class NotifyEntityPlatform:
    """No simple base class in NotifyEntity to reuse, plus lack of support for Context passing"""

    @abc.abstractmethod
    async def async_send_message(
        self, message: str, title: str | None = None, target: str | None = None, context: HAContext | None = None
    ) -> None:
        """implement message"""
