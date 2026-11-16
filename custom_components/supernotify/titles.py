"""Titles of recipient and transport subentries, prefixed by their type in Home Assistant's language.

Home Assistant lists an integration's subentries by title alone, sorted, with no grouping by type,
so the prefix keeps the recipients together and the transports together. A title is stored text,
not a translation key, so the prefix is in the language at the time, and replaced at start up
should Home Assistant's language have changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.core import callback
from homeassistant.helpers.translation import async_get_cached_translations, async_get_translations

from . import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

SEPARATOR: Final[str] = " - "
# the languages Supernotify is translated into, to recognise a title's prefix in any of them
LANGUAGES: Final[tuple[str, ...]] = ("de", "en", "es", "fr", "hi", "it", "ja", "nl", "pl", "pt", "zh-Hans")
_CATEGORY: Final[str] = "config_subentries"


async def async_load_titles(hass: HomeAssistant) -> None:
    """Cache each subentry type's name, its `entry_type` translation, in every language, for subentry_title()"""
    for language in {*LANGUAGES, hass.config.language}:
        await async_get_translations(hass, language, _CATEGORY, [DOMAIN])


@callback
def subentry_title(hass: HomeAssistant, subentry_type: str, name: str) -> str:
    """`name` prefixed by the subentry type's name in Home Assistant's language, e.g. "Recipient - Alice",
    replacing any prefix it has already, in any language"""
    for language in LANGUAGES:
        type_name: str | None = _type_name(hass, subentry_type, language)
        if type_name and name.startswith(f"{type_name}{SEPARATOR}"):
            name = name.removeprefix(f"{type_name}{SEPARATOR}")
            break
    type_name = (
        _type_name(hass, subentry_type, hass.config.language)
        or _type_name(hass, subentry_type, "en")
        or subentry_type.capitalize()
    )
    return f"{type_name}{SEPARATOR}{name}"


def _type_name(hass: HomeAssistant, subentry_type: str, language: str) -> str | None:
    return async_get_cached_translations(hass, language, _CATEGORY, DOMAIN).get(
        f"component.{DOMAIN}.{_CATEGORY}.{subentry_type}.entry_type"
    )
