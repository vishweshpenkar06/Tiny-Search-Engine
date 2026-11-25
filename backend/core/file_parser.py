import csv
import hashlib
import html
import io
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from core.models import ParsedDocument


_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".csv": "text/csv",
}
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
_SKIP_TAGS = frozenset(("script", "style", "noscript", "template"))
_HEADING_TAGS = frozenset(("h1", "h2", "h3", "h4", "h5", "h6"))


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.headings: list[str] = []
        self.body_parts: list[str] = []
        self._title = False
        self._heading = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag == "title":
            self._title = True
        elif self._skip_depth == 0 and tag in _HEADING_TAGS:
            self._heading = True
            self.headings.append("")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._title = False
        elif tag in _HEADING_TAGS:
            self._heading = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = html.unescape(data)
        if self._title:
            self.title_parts.append(value)
        if self._heading and self.headings:
            self.headings[-1] += value
        self.body_parts.append(value)


def _decode(data: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _flatten(*parts: object) -> str:
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, (list, tuple)):
            chunks.extend(str(item) for item in part if item)
        elif part:
            chunks.append(str(part))
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def parse_file(
    path: str,
    source_type: str = "upload",
    source_url: str | None = None,
    filename: str | None = None,
) -> ParsedDocument:
    file_path = Path(path)
    name = filename or file_path.name
    extension = Path(name).suffix.lower()
    if extension not in _TYPES:
        raise ValueError(f"Unsupported file type: {extension or name}")
    if not file_path.is_file():
        raise ValueError(f"File not found: {path}")

    raw = file_path.read_bytes()
    text = _decode(raw)
    title = ""
    headings: tuple[str, ...] = ()
    body = text

    if extension in (".html", ".htm"):
        parser = _HTMLText()
        parser.feed(text)
        parser.close()
        title = _flatten(*parser.title_parts)
        headings = tuple(_flatten(item) for item in parser.headings if _flatten(item))
        body = _flatten(*parser.body_parts)
    elif extension == ".md":
        matches = list(_HEADING_RE.finditer(text))
        headings = tuple(_flatten(match.group(2)) for match in matches if _flatten(match.group(2)))
        title = headings[0] if headings else _first_line(text)
        body = _flatten(_HEADING_RE.sub(lambda match: match.group(2), text))
    elif extension == ".csv":
        try:
            rows = list(csv.reader(io.StringIO(text)))
        except csv.Error:
            rows = []
        title = _flatten(*rows[0]) if rows else ""
        body = _flatten(*(cell for row in rows for cell in row))
    else:
        title = _first_line(text)
        body = _flatten(text)

    content = _flatten(body)
    content_hash = hashlib.sha256(raw).hexdigest()
    word_count = len(_TOKEN_RE.findall(content))
    indexed_at = datetime.now(timezone.utc).isoformat()
    return ParsedDocument(
        source_key=content_hash,
        filename=name,
        source_type=source_type,
        source_url=source_url,
        title=title,
        headings=headings,
        body=body,
        content=content,
        content_hash=content_hash,
        byte_size=len(raw),
        word_count=word_count,
        indexed_at=indexed_at,
        file_type=_TYPES[extension],
    )


class FileParser:
    @staticmethod
    def parse_file(filepath: str, source_type: str = "upload", source_url=None, filename=None):
        return parse_file(filepath, source_type, source_url, filename)
