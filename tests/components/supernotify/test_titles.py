from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from custom_components.supernotify.titles import LANGUAGES, async_load_titles, subentry_title

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_title_prefixed_in_home_assistant_language(hass: HomeAssistant) -> None:
    hass.config.language = "de"
    await async_load_titles(hass)

    assert subentry_title(hass, "recipient", "Alice") == "Empfänger - Alice"
    assert subentry_title(hass, "transport", "Generic") == "Transport - Generic"


async def test_title_replaces_a_prefix_in_any_language(hass: HomeAssistant) -> None:
    """As when Home Assistant's language has changed since the title was given"""
    hass.config.language = "de"
    await async_load_titles(hass)

    assert subentry_title(hass, "recipient", "Recipient - Alice") == "Empfänger - Alice"
    assert subentry_title(hass, "recipient", "Destinataire - Alice") == "Empfänger - Alice"
    assert subentry_title(hass, "recipient", "Empfänger - Alice") == "Empfänger - Alice"


async def test_title_in_english_for_an_untranslated_language(hass: HomeAssistant) -> None:
    hass.config.language = "sv"
    await async_load_titles(hass)

    assert subentry_title(hass, "recipient", "Alice") == "Recipient - Alice"


def test_title_before_translations_are_loaded(hass: HomeAssistant) -> None:
    assert subentry_title(hass, "recipient", "Alice") == "Recipient - Alice"


def test_languages_are_those_translated() -> None:
    translations = Path(__file__).parents[3] / "custom_components" / "supernotify" / "translations"
    assert sorted(LANGUAGES) == sorted(p.stem for p in translations.glob("*.json"))
