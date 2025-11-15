"""Miscellaneous helper functions.

No dependencies permitted
"""

from dataclasses import dataclass, field
from typing import Any


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

    def contents(self) -> dict[str, Any]:
        result = {
            "domain": self.domain,
            "action": self.action,
            "action_data": self.action_data,
            "elapsed": self.elapsed,
        }
        if self.target_data is not None:
            result["target_data"] = self.target_data
        if self.exception is not None:
            result["exception"] = self.exception
        return result
