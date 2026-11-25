from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}


@dataclass(frozen=True)
class ExtractedPage:
    title: str
    headings: tuple[str, ...]
    body: str
    links: tuple[str, ...] = field(default_factory=tuple)

    @property
    def content(self) -> str:
        parts = [self.title, *self.headings, self.body]
        return "\n".join(part for part in parts if part).strip()


def _clean(text: str) -> str:
    return " ".join(text.split())


class PageExtractor(HTMLParser):
    def __init__(self, base_url: str | None = None):
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._skip_depth = 0
        self._capture: str | None = None
        self._title_parts: list[str] = []
        self._heading_parts: list[str] = []
        self._headings: list[str] = []
        self._body_parts: list[str] = []
        self._links: list[str] = []
        self._seen_links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        self._body_parts.append(" ")
        if tag == "title":
            self._capture = "title"
        elif tag in _HEADING_TAGS:
            self._capture = "heading"
            self._heading_parts = []
        elif tag == "a":
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            if href:
                self._add_link(href)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        self._body_parts.append(" ")
        if tag == "title" and self._capture == "title":
            self._capture = None
        elif tag in _HEADING_TAGS and self._capture == "heading":
            heading = _clean("".join(self._heading_parts))
            if heading:
                self._headings.append(heading)
                self._body_parts.append(heading)
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        if self._capture == "title":
            self._title_parts.append(data)
        elif self._capture == "heading":
            self._heading_parts.append(data)
        self._body_parts.append(data)

    def result(self) -> ExtractedPage:
        return ExtractedPage(
            title=_clean("".join(self._title_parts)),
            headings=tuple(self._headings),
            body=_clean("".join(self._body_parts)),
            links=tuple(self._links),
        )

    def _add_link(self, href: str) -> None:
        value = href.strip()
        if not value or value.startswith("#"):
            return
        resolved = urljoin(self._base_url, value) if self._base_url else value
        parts = urlsplit(resolved)
        if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
            return
        normalized = resolved.split("#", 1)[0]
        if normalized in self._seen_links:
            return
        self._seen_links.add(normalized)
        self._links.append(normalized)


def extract_html(html: str, base_url: str | None = None) -> ExtractedPage:
    parser = PageExtractor(base_url)
    parser.feed(html or "")
    parser.close()
    return parser.result()
