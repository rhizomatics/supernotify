from pathlib import Path
from typing import Any

from properdocs.structure.nav import Link
from properdocs.utils.meta import get_data

# Top level tabs, in display order, keyed by page source file or section title.
# Page titles aren't resolved yet when the nav is built, so pages are matched by file.
TAB_ORDER = [
    "index.md",
    "Quick start",
    "Recipes",
    "Usage",
    "Configuration",
    "Transports",
    "Developer",
    "changelog.md",
]
HIDDEN_TABS: set[str] = set()
# Section titles come from folder names, which can't carry capitalization like "RFCs" without it leaking into URLs
SECTION_TITLES = {"Rfcs": "RFCs", "Quick start": "Quick Start"}
# Sub-sections to list first within a section, by (retitled) section title; others keep folder order after them
SUBSECTION_ORDER = {"Developer": ["RFCs"]}
# Pages to list in reading order within a section, by (retitled) section title and file name
PAGE_ORDER = {
    "Quick Start": [
        "index.md",
        "installation.md",
        "first_notification.md",
        "next_steps.md",
        "basic_concepts.md",
        "advanced_concepts.md",
        "removing.md",
    ],
}
# Sections listed in the sidebar as the tags of their pages, each a link to the section's tagged
# index narrowed to that tag, rather than as a list of pages repeating that index
TAG_NAV = {"Recipes"}
# Words in tag names that plain capitalization gets wrong
TAG_WORDS = {
    "433mhz": "433MHz",
    "api": "API",
    "appdaemon": "AppDaemon",
    "genai": "GenAI",
    "html": "HTML",
    "ios": "iOS",
    "macos": "macOS",
    "mqtt": "MQTT",
    "opentelemetry": "OpenTelemetry",
    "ptz": "PTZ",
    "rest": "REST",
    "sms": "SMS",
    "tts": "TTS",
    "yaml": "YAML",
}


def _key(item: Any) -> str:  # ruff: ignore[any-type]
    file = getattr(item, "file", None)
    return file.src_uri if file else item.title


def _tag_links(section: Any) -> list[Any]:  # ruff: ignore[any-type]
    """The section's index page, then a link for each tag its pages have and its index doesn't hide."""
    index = next(c for c in section.children if getattr(c, "file", None) and c.file.name == "index")
    hidden: set[str] = set(get_data(index.file.content_string)[1].get("hidden_tags") or [])
    tags: set[str] = set()
    for child in section.children:
        if child is not index and getattr(child, "file", None):
            tags.update(get_data(child.file.content_string)[1].get("tags") or [])
    links: list[Any] = []
    for tag in sorted(tags - hidden):
        label = " ".join(TAG_WORDS.get(word, word.capitalize()) for word in tag.split("_"))
        link = Link(label, f"{index.file.url}#tag={tag}")
        link.parent = section
        links.append(link)
    return [index, *links]


def _retitle_sections(items: list[Any]) -> None:
    for item in items:
        if getattr(item, "is_section", False):
            item.title = SECTION_TITLES.get(item.title, item.title)
            _retitle_sections(item.children)
            if item.title in TAG_NAV:
                # the pages keep the section as their parent, so tabs and breadcrumbs still work
                item.children = _tag_links(item)
            pages = PAGE_ORDER.get(item.title)
            if pages:
                item.children.sort(key=lambda c: pages.index(Path(_key(c)).name) if Path(_key(c)).name in pages else len(pages))
            first = SUBSECTION_ORDER.get(item.title)
            if first:
                # stable sort, so pages and unlisted sub-sections keep their folder order
                item.children.sort(
                    key=lambda c: (
                        getattr(c, "is_section", False),
                        first.index(c.title) if c.title in first else len(first),
                    )
                )


def on_nav(nav: Any, config: Any, files: Any, **kwargs: Any) -> Any:  # ruff: ignore[any-type]
    """Order the top navigation tabs, optionally hiding some of them.

    The nav is auto-generated from the docs folder, so reorder it here rather
    than listing every page in an explicit nav.
    """
    items = [item for item in nav.items if _key(item) not in HIDDEN_TABS]
    items.sort(key=lambda item: TAB_ORDER.index(_key(item)) if _key(item) in TAB_ORDER else len(TAB_ORDER))
    _retitle_sections(items)
    nav.items = items
    return nav
