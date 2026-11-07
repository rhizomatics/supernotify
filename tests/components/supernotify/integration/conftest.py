from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from homeassistant.core import HomeAssistant
from .framework import House
from .houses import HOUSES


async def _house(hass: HomeAssistant, name: str) -> AsyncGenerator[House]:
    """The house of that name in houses.py"""
    spec: dict[str, Any] = dict(HOUSES[name])
    if "config" in spec:
        spec["config"] = (Path(__file__).parent / spec["config"]).read_text()
    house = House(**spec)
    await house.setup(hass)
    try:
        yield house
    finally:
        house.cleanup()


@pytest.fixture
async def preview_house(hass: HomeAssistant) -> AsyncGenerator[House]:
    async for house in _house(hass, "preview_house"):
        yield house


@pytest.fixture
async def starter_flat(hass: HomeAssistant) -> AsyncGenerator[House]:
    async for house in _house(hass, "starter_flat"):
        yield house


@pytest.fixture
async def town_house(hass: HomeAssistant) -> AsyncGenerator[House]:
    async for house in _house(hass, "town_house"):
        yield house


@pytest.fixture
async def smart_villa(hass: HomeAssistant) -> AsyncGenerator[House]:
    async for house in _house(hass, "smart_villa"):
        yield house
