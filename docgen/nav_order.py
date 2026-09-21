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
HIDDEN_TABS = {"tags.md"}


def _key(item: Any) -> str:  # ruff: ignore[any-type]
    file = getattr(item, "file", None)
    return file.src_uri if file else item.title


def on_nav(nav: Any, config: Any, files: Any, **kwargs: Any) -> Any:  # ruff: ignore[any-type]
    """Order the top navigation tabs and hide the Tags tab.

    The nav is auto-generated from the docs folder, so reorder it here rather
    than listing every page in an explicit nav. The Tags page is still built,
    it just isn't linked from the top navigation.
    """
    items = [item for item in nav.items if _key(item) not in HIDDEN_TABS]
    items.sort(key=lambda item: TAB_ORDER.index(_key(item)) if _key(item) in TAB_ORDER else len(TAB_ORDER))
    nav.items = items
    return nav
