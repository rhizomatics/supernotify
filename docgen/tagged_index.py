"""Build a page index from each page's own front matter, with its tags as coloured bubbles."""

import html
import posixpath
import zlib
from typing import Any

from properdocs.utils.meta import get_data

MARKER = "{{ tagged_index }}"


def _bubble(tag: str) -> str:
    # the colour comes from the tag's own name, so a tag is the same colour wherever it is shown
    hue = zlib.crc32(tag.encode()) % 360
    # a button, so docs/javascripts/tag_filter.js can narrow the list to a tag by mouse or keyboard
    return f'<button type="button" class="index-tag" style="--tag-hue: {hue}" aria-pressed="false">{html.escape(tag)}</button>'


def on_page_markdown(markdown: str, page: Any, files: Any, **kwargs: Any) -> str:  # ruff: ignore[any-type]
    """Replace the marker with a list of the other pages in the same folder, in title order.

    Tags named in `hidden_tags` in the front matter of the index page are left out of it, so
    the pages can be tagged in more detail than is useful to show here.
    """
    if MARKER not in markdown:
        return markdown
    hidden: set[str] = set(page.meta.get("hidden_tags") or [])
    folder = posixpath.dirname(page.file.src_uri)
    entries: list[tuple[str, str]] = []
    for file in files.documentation_pages():
        if posixpath.dirname(file.src_uri) != folder or file.src_uri == page.file.src_uri:
            continue
        # the other pages haven't been read yet, so their titles and tags aren't on a Page to ask
        _, meta = get_data(file.content_string)
        tags = "".join(_bubble(tag) for tag in dict.fromkeys(meta.get("tags") or []) if tag not in hidden)
        title = str(meta.get("title") or file.name)
        entries.append((title.casefold(), f"- [{title}]({posixpath.basename(file.src_uri)}) {tags}".rstrip()))
    return markdown.replace(MARKER, "\n".join(line for _, line in sorted(entries)))
