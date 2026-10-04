"""Tests for supernotify.snooze: snooze, silence and resume from scripts, automations and dashboards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.model import CommandType, GlobalTargetType, QualifiedTargetType, RecipientType

from .test_switch import _config, _setup

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.engine import SupernotifyEngine
    from custom_components.supernotify.snoozer import Snooze


async def _snooze(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    response = await hass.services.async_call(DOMAIN, "snooze", data, blocking=True, return_response=True)
    await hass.async_block_till_done()
    assert response is not None
    return dict(response)


def _only(engine: SupernotifyEngine) -> Snooze:
    snoozes = list(engine.context.snoozer.snoozes.values())
    assert len(snoozes) == 1
    return snoozes[0]


async def test_snooze_everything_for_everyone_by_default(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())

    response = await _snooze(hass, {"command": "snooze", "minutes": 30})

    snooze = _only(engine)
    assert snooze.target_type == GlobalTargetType.EVERYTHING
    assert snooze.recipient_type == RecipientType.EVERYONE
    assert snooze.reason == "Action"
    assert snooze.snooze_until is not None
    assert 29 * 60 < (snooze.snooze_until - snooze.snoozed_at).total_seconds() <= 30 * 60
    assert response == {"snoozes": engine.enquire_snoozes()}
    assert len(response["snoozes"]) == 1


async def test_snooze_without_minutes_uses_configured_time(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())

    await _snooze(hass, {"command": "snooze", "scope": "noncritical"})

    snooze = _only(engine)
    assert snooze.target_type == GlobalTargetType.NONCRITICAL
    assert snooze.snooze_until - snooze.snoozed_at == engine.context.snoozer.snooze_period


async def test_silence_one_delivery_for_one_person_with_reason(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())

    await _snooze(
        hass, {"command": "silence", "scope": "delivery", "name": "testing", "person": "person.joe", "reason": "Dashboard"}
    )

    snooze = _only(engine)
    assert snooze.target_type == QualifiedTargetType.DELIVERY
    assert snooze.target == "testing"
    assert snooze.recipient_type == RecipientType.USER
    assert snooze.recipient == "person.joe"
    assert snooze.snooze_until is None
    assert snooze.reason == "Dashboard"


async def test_resume_removes_the_matching_snooze_only(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    await _snooze(hass, {"command": "silence", "scope": "delivery", "name": "testing", "person": "person.joe"})
    await _snooze(hass, {"command": "snooze", "scope": "noncritical"})
    assert len(engine.context.snoozer.snoozes) == 2

    response = await _snooze(hass, {"command": "resume", "scope": "delivery", "name": "testing", "person": "person.joe"})

    assert _only(engine).target_type == GlobalTargetType.NONCRITICAL
    assert len(response["snoozes"]) == 1


async def test_name_is_ignored_for_global_scopes(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())

    await _snooze(hass, {"command": "snooze", "scope": "everything", "name": "testing"})

    assert _only(engine).target is None


async def test_works_without_a_response(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())

    assert await hass.services.async_call(DOMAIN, "snooze", {"command": "silence"}, blocking=True) is None
    await hass.async_block_till_done()
    assert _only(engine).snooze_until is None


@pytest.mark.parametrize(
    ("data", "error"),
    [
        ({"command": "snooze", "scope": "delivery"}, "A name is needed"),
        ({"command": "snooze", "scope": "delivery", "name": "nope"}, "Unknown delivery 'nope'"),
        ({"command": "snooze", "scope": "camera", "name": "driveway"}, "entity_id"),
        ({"command": "snooze", "scope": "tag", "name": "no such thing"}, "No scenario or entity"),
        ({"command": "snooze", "person": "person.stranger"}, "not a recipient"),
    ],
)
async def test_invalid_snooze_is_refused(hass: HomeAssistant, data: dict[str, Any], error: str) -> None:
    engine = await _setup(hass, _config())

    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call(DOMAIN, "snooze", data, blocking=True)

    assert exc.value.translation_key == "invalid_snooze"
    assert error in exc.value.translation_placeholders["error"]
    assert engine.context.snoozer.snoozes == {}


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"command": "normal"},
        {"command": "snooze", "scope": "mobile"},
        {"command": "snooze", "minutes": 0},
        {"command": "snooze", "person": "switch.joe"},
    ],
)
async def test_schema_rejects_bad_fields(hass: HomeAssistant, data: dict[str, Any]) -> None:
    await _setup(hass, _config())

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "snooze", data, blocking=True)


async def test_tag_can_be_resumed_after_what_it_named_has_gone(hass: HomeAssistant) -> None:
    engine = await _setup(hass, _config())
    engine.context.snoozer.register_snooze(
        CommandType.SILENCE, QualifiedTargetType.TAG, "gone_camera", RecipientType.EVERYONE, None, None
    )

    await _snooze(hass, {"command": "resume", "scope": "tag", "name": "gone_camera"})

    assert engine.context.snoozer.snoozes == {}
