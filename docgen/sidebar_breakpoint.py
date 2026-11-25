"""Pin the navigation sidebar from 60em (960px) wide, rather than the theme's 76.25em (1220px).

The theme has no setting for this, and uses the breakpoint in its JavaScript, to position the
sidebar, as well as in its stylesheet, so both are rewritten after the build to keep them in step.
docs/javascripts/nav_toggle.js adds a button to hide the sidebar.
"""

import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(f"properdocs.hooks.{__name__}")

THEME_ASSETS = ("**/assets/stylesheets/main.*.min.css", "**/assets/javascripts/bundle.*.min.js")
# the theme's last width below the breakpoint, then the breakpoint itself
REPLACEMENTS = (("76.234375em", "59.984375em"), ("76.25em", "60em"))


def on_post_build(config: Any, **kwargs: Any) -> None:  # ruff: ignore[any-type]
    site = Path(config["site_dir"])
    for pattern in THEME_ASSETS:
        paths = list(site.glob(pattern))
        if not paths:
            _LOGGER.warning("No theme asset matching %s, so the sidebar breakpoint is unchanged", pattern)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            if not any(old in text for old, _new in REPLACEMENTS):
                _LOGGER.warning("No sidebar breakpoint found in %s, so it is unchanged", path)
                continue
            for old, new in REPLACEMENTS:
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")
