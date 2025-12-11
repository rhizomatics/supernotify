"""Miscellaneous helper functions.

No same pkg dependencies permitted
"""

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cachetools import TTLCache
from homeassistant.helpers.typing import ConfigType

from . import (
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    CONF_DUPE_POLICY,
    CONF_SIZE,
    CONF_TTL,
)

_LOGGER = logging.getLogger(__name__)


def safe_get(probably_a_dict: dict[Any, Any] | None, key: Any, default: Any = None) -> Any:
    probably_a_dict = probably_a_dict or {}
    return probably_a_dict.get(key, default)


def safe_extend(target: list[Any], extension: list[Any] | tuple[Any] | Any) -> list[Any]:
    if target is None:
        target = []
    elif not isinstance(target, list):
        target = [target]
    if isinstance(extension, list | tuple):
        target.extend(extension)
    elif extension:
        target.append(extension)
    return target


def ensure_list(v: Any) -> list[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    if isinstance(v, tuple):
        return list(v)
    return [v]


def ensure_dict(v: Any, default: Any = None) -> dict[Any, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return v
    if isinstance(v, set | list):
        return dict.fromkeys(v, default)
    return {v: default}


@dataclass
class CallRecord:
    elapsed: float = field()
    domain: str | None = field(default=None)
    action: str | None = field(default=None)
    action_data: dict[str, Any] | None = field(default=None)
    target_data: dict[str, Any] | None = field(default=None)
    exception: str | None = field(default=None)
    debug: bool = field(default=False)
    service_response: dict[str, Any] | None = field(default=None)

    def contents(self, **_kwargs: Any) -> dict[str, Any]:
        result = {
            "domain": self.domain,
            "action": self.action,
            "action_data": self.action_data,
            "elapsed": self.elapsed,
            "debug": self.debug,
        }
        if self.target_data is not None:
            result["target_data"] = self.target_data
        if self.exception is not None:
            result["exception"] = self.exception
        if self.service_response is not None:
            result["service_response"] = self.service_response
        return result


class DupeCheckable:
    id: str
    priority: str

    @abstractmethod
    def skip_priorities(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def hash(self) -> int:
        raise NotImplementedError


class DupeChecker:
    def __init__(self, dupe_check_config: ConfigType) -> None:
        self.policy = dupe_check_config.get(CONF_DUPE_POLICY, ATTR_DUPE_POLICY_MTSLP)
        # dupe check cache, key is (priority, message hash)
        self.cache: TTLCache[tuple[int, str], str] = TTLCache(
            maxsize=dupe_check_config.get(CONF_SIZE, 100), ttl=dupe_check_config.get(CONF_TTL, 120)
        )

    def check(self, dupe_candidate: DupeCheckable) -> bool:
        if self.policy == ATTR_DUPE_POLICY_NONE:
            return False
        hashed: int = dupe_candidate.hash()
        same_or_higher_priority: list[str] = dupe_candidate.skip_priorities()
        dupe = False
        if any((hashed, p) in self.cache for p in same_or_higher_priority):
            _LOGGER.debug("SUPERNOTIFY Detected dupe: %s", dupe_candidate.id)
            dupe = True
        self.cache[hashed, dupe_candidate.priority] = dupe_candidate.id
        return dupe
