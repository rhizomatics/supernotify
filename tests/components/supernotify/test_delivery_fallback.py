"""A delivery's own `fallback:` list: when it fails and sends nothing, the listed deliveries are
tried in order until one sends."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.supernotify import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _delivery(action: str, **extra: Any) -> dict[str, Any]:
    return {"transport": "generic", "action": action, "target": ["testy.testy"], **extra}


async def _setup(
    hass: HomeAssistant, deliveries: dict[str, Any], failing: tuple[str, ...] = ()
) -> dict[str, list[ServiceCall]]:
    calls: dict[str, list[ServiceCall]] = {}
    for name in ("a", "b", "c"):
        if name in failing:

            async def fail(_call: ServiceCall) -> None:
                raise HomeAssistantError("down")

            hass.services.async_register("test", name, fail)
        else:
            calls[name] = async_mock_service(hass, "test", name)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"delivery": deliveries}})
    await hass.async_block_till_done()
    return calls


async def _notify(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN, "notify", {"message": "gate open", **data}, blocking=True, return_response=True
    )
    await hass.async_block_till_done()
    assert response is not None
    return dict(response)


async def test_fallback_used_when_the_delivery_fails(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["google", "push"]),
            "google": _delivery("test.b", inclusion="fallback"),
            "push": _delivery("test.c", inclusion="fallback"),
        },
        failing=("a",),
    )

    result = await _notify(hass, delivery=["alexa"])

    assert len(calls["b"]) == 1  # the first fallback sent, so the second wasn't needed
    assert calls["c"] == []
    assert "success" in result["deliveries"]["google"]
    assert result["delivery_provenance"]["google"]["enabled_by"] == ["fallback:alexa"]


async def test_next_fallback_tried_when_the_first_fails_too(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["google", "push"]),
            "google": _delivery("test.b", inclusion="fallback"),
            "push": _delivery("test.c", inclusion="fallback"),
        },
        failing=("a", "b"),
    )

    result = await _notify(hass, delivery=["alexa"])

    assert len(calls["c"]) == 1
    assert "error" in result["deliveries"]["google"]
    assert "success" in result["deliveries"]["push"]


async def test_no_fallback_when_the_delivery_succeeds(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["google"]),
            "google": _delivery("test.b", inclusion="fallback"),
        },
    )

    result = await _notify(hass, delivery=["alexa"])

    assert len(calls["a"]) == 1
    assert calls["b"] == []
    assert "google" not in result["deliveries"]


async def test_fallback_that_already_sent_is_not_sent_twice(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["push"]),
            "push": _delivery("test.c"),
        },
        failing=("a",),
    )

    await _notify(hass, delivery=["alexa", "push"])

    assert len(calls["c"]) == 1


async def test_only_one_level_and_switched_off_fallbacks_skipped(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["google"]),
            "google": _delivery("test.b", inclusion="fallback", fallback=["push"]),
            "push": _delivery("test.c", inclusion="fallback", enabled=False),
        },
        failing=("a", "b"),
    )

    result = await _notify(hass, delivery=["alexa"])

    # google failed as alexa's fallback, but its own fallback isn't followed
    assert calls["c"] == []
    assert "push" not in result["deliveries"]


async def test_switched_off_fallback_is_skipped_for_the_next(hass: HomeAssistant) -> None:
    calls = await _setup(
        hass,
        {
            "alexa": _delivery("test.a", fallback=["google", "push"]),
            "google": _delivery("test.b", inclusion="fallback", enabled=False),
            "push": _delivery("test.c", inclusion="fallback"),
        },
        failing=("a",),
    )

    await _notify(hass, delivery=["alexa"])

    assert calls["b"] == []
    assert len(calls["c"]) == 1


async def test_unknown_fallback_is_warned_at_startup(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    await _setup(hass, {"alexa": _delivery("test.a", fallback=["nope", "alexa"])})

    assert "Delivery alexa has fallback nope, which is not another delivery" in caplog.text
    assert "Delivery alexa has fallback alexa, which is not another delivery" in caplog.text
