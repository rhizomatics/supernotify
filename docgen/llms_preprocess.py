from pathlib import Path

from bs4 import BeautifulSoup

# llmstxt plugin preprocess: put each page's own URL under its title, as a "Source:" line, so
# something reading the combined llms-full.txt - like Supernotify's help tool - can link to
# the page it found. The plugin only passes the page's output .md path, so the URL is worked out
# from where that sits in the site directory.

# Keep in step with the llmstxt plugin's base_url in properdocs.yml
BASE_URL = "https://supernotify.rhizomatics.org.uk/latest/"
# properdocs' default site_dir, next to properdocs.yml - mike builds there too
SITE_DIR = Path(__file__).parent.parent / "site"


def preprocess(soup: BeautifulSoup, output: str) -> None:
    page = Path(output).resolve().relative_to(SITE_DIR.resolve()).as_posix()
    url = BASE_URL + page.removesuffix("index.md")
    source = soup.new_tag("p")
    source.string = f"Source: {url}"
    if title := soup.find("h1"):
        title.insert_after(source)
    else:
        soup.insert(0, source)
