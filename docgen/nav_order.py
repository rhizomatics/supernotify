from typing import Any

# Top level tabs, in display order, keyed by page source file or section title.
# Page titles aren't resolved yet when the nav is built, so pages are matched by file.
TAB_ORDER = [
    "index.md",
    "getting_started.md",
    "concepts.md",
    "Recipes",
    "Usage",
    "Configuration",
    "Transports",
    "Developer",
    "changelog.md",
]
HIDDEN_TABS: set[str] = set()
# Section titles come from folder names, which can't carry capitalization like "RFCs" without it leaking into URLs
SECTION_TITLES = {"Rfcs": "RFCs"}
# Sub-sections to list first within a section, by (retitled) section title; others keep folder order after them
SUBSECTION_ORDER = {"Developer": ["RFCs"]}


def _key(item: Any) -> str:  # ruff: ignore[any-type]
    file = getattr(item, "file", None)
    return file.src_uri if file else item.title


def _retitle_sections(items: list[Any]) -> None:
    for item in items:
        if getattr(item, "is_section", False):
            item.title = SECTION_TITLES.get(item.title, item.title)
            _retitle_sections(item.children)
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
