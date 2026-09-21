import logging
import subprocess
from pathlib import Path
from shutil import which
from typing import Any

log = logging.getLogger("mkdocs.hooks.optimize_social_cards")


def on_post_build(config: dict[str, Any], **kwargs: Any) -> None:
    """Compress generated social card PNGs with pngquant.

    The 'social' plugin composites cards after the 'optimize' plugin has
    already claimed the docs media files, so the generated cards (often
    ~800KB each due to the background image) never pass through pngquant.
    Multiplied across every mike-deployed version, this bloats gh-pages.
    """
    social_dir = Path(config["site_dir"]) / "assets" / "images" / "social"
    if not social_dir.is_dir():
        return

    cards = list(social_dir.rglob("*.png"))
    if not cards:
        return

    if not which("pngquant"):
        log.warning("pngquant not found, skipping social card optimization")
        return

    subprocess.run(["pngquant", "--force", "--skip-if-larger", "--ext", ".png", *map(str, cards)], check=False)
