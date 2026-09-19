"""Every `supernotify.notify` example in the docs must be a call the action would accept, in the
current (non-legacy) shape - the docs are what users copy, and a wrong example otherwise only
surfaces as a bug report."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import voluptuous as vol
import yaml

from custom_components.supernotify.actions import lift_legacy_nested_data
from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA

ROOT = Path(__file__).parents[3]
ACTION = "supernotify.notify"
# a sanity floor, so a parsing regression can't silently turn this into a test of nothing
MIN_EXAMPLES = 20


class _Unresolved:
    """Stands in for values only known at runtime, e.g. blueprint `!input`"""


class _DocLoader(yaml.SafeLoader):
    pass


_DocLoader.add_multi_constructor("!", lambda _loader, _suffix, _node: _Unresolved())


def _is_runtime_value(value: object) -> bool:
    return isinstance(value, _Unresolved) or (isinstance(value, str) and ("{{" in value or "{%" in value))


def _prune_runtime_values(obj: object) -> object:
    """Drop values Home Assistant would only resolve at call time, which can't be schema checked"""
    if isinstance(obj, dict):
        return {k: _prune_runtime_values(v) for k, v in obj.items() if not _is_runtime_value(v)}
    if isinstance(obj, list):
        return [_prune_runtime_values(v) for v in obj if not _is_runtime_value(v)]
    return obj


def _dicts(obj: object) -> Iterator[dict[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _dicts(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _dicts(value)


def _yaml_blocks(path: Path) -> Iterator[tuple[int, str]]:
    text = path.read_text()
    if path.suffix == ".yaml":
        yield 1, text
        return
    for match in re.finditer(r"```ya?ml[^\n]*\n(.*?)```", text, re.DOTALL):
        yield text[: match.start(1)].count("\n") + 1, match.group(1)


def _blocks() -> list[Any]:
    """Every YAML block that mentions the action, whether or not it turns out to parse"""
    found = []
    for path in [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *sorted((ROOT / "examples").rglob("*.yaml"))]:
        for line, block in _yaml_blocks(path):
            if ACTION in block:
                found.append(pytest.param(block, id=f"{path.relative_to(ROOT)}:{line}"))
    return found


def _examples() -> list[Any]:
    found = []
    for param in BLOCKS:
        try:
            doc = yaml.load(param.values[0], _DocLoader)
        except yaml.YAMLError:
            continue  # reported by test_docs_block_is_valid_yaml
        for index, call in enumerate(_dicts(doc)):
            if (call.get("action") or call.get("service")) == ACTION and isinstance(call.get("data"), dict):
                payload = dict(call["data"])
                if "target" in call:
                    payload.setdefault("target", call["target"])
                found.append(pytest.param(payload, id=f"{param.id}#{index}"))
    return found


BLOCKS = _blocks()
EXAMPLES = _examples()


@pytest.mark.parametrize("block", BLOCKS)
def test_docs_block_is_valid_yaml(block: str) -> None:
    """Skipping blocks that don't parse would hide exactly the copy-paste failures this guards against"""
    try:
        yaml.load(block, _DocLoader)
    except yaml.YAMLError as e:
        pytest.fail(f"docs example is not valid YAML: {e}")


def test_docs_examples_were_found() -> None:
    assert len(EXAMPLES) >= MIN_EXAMPLES


def _checkable(payload: dict[str, Any]) -> dict[str, Any]:
    """Payload minus values only resolved at call time, but always with a message, which the schema requires"""
    pruned = cast("dict[str, Any]", _prune_runtime_values(payload))
    pruned.setdefault("message", "placeholder")
    return pruned


@pytest.mark.parametrize("payload", EXAMPLES)
def test_docs_example_is_valid_action_call(payload: dict[str, Any]) -> None:
    assert "message" in payload, "supernotify.notify requires a message"
    try:
        NOTIFY_ACTION_SCHEMA(_checkable(payload))
    except vol.Invalid as e:
        pytest.fail(f"docs example rejected by supernotify.notify schema: {e}")


@pytest.mark.parametrize("payload", EXAMPLES)
def test_docs_example_does_not_use_legacy_nested_data(payload: dict[str, Any]) -> None:
    # unpruned: only keys matter here, and a templated value must not hide the key it belongs to
    if lift_legacy_nested_data(payload) != payload:  # not an assert - diffing large payloads can crash xdist workers
        pytest.fail("Supernotify fields belong at top level, not inside `data:`")
