import gzip
import hashlib
import http.client
import ipaddress
import socket
import ssl
import time
import zlib
from dataclasses import dataclass
from typing import Callable, Iterator
from urllib.parse import urljoin, urlsplit, urlunsplit

from config import Config
from crawler.extract import extract_html
from crawler.robots import RobotsRules, parse_robots


class CrawlError(Exception):
    pass


@dataclass(frozen=True)
class CrawlLimits:
    max_pages: int = 50
    max_depth: int = 2
    max_redirects: int = 5
    timeout: float = 10.0
    max_response_bytes: int = 5 * 1024 * 1024
    max_decompressed_bytes: int = 10 * 1024 * 1024
    max_time: float = 30.0
    user_agent: str = "TinySearchBot/1.0 (+https://example.invalid/bot)"


@dataclass(frozen=True)
class ValidatedTarget:
    scheme: str
    host: str
    port: int
    address: str

    @property
    def origin(self) -> str:
        default = 443 if self.scheme == "https" else 80
        suffix = "" if self.port == default else f":{self.port}"
        return f"{self.scheme}://{self.host}{suffix}"


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str
    status: int
    content_type: str
    body: str


@dataclass(frozen=True)
class CrawledPage:
    url: str
    depth: int
    title: str
    headings: tuple[str, ...]
    body: str
    text: str
    links: tuple[str, ...]
    content_hash: str


def limits_from_config(
    config: Config | None = None,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> CrawlLimits:
    maximum = getattr(config, "max_content_length", 5 * 1024 * 1024)
    return CrawlLimits(
        max_pages=max_pages if max_pages is not None else 50,
        max_depth=max_depth if max_depth is not None else 2,
        max_response_bytes=min(maximum, 5 * 1024 * 1024),
    )


def _is_safe_address(value: str, allow_loopback: bool) -> bool:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            address = mapped
    if allow_loopback and address.is_loopback:
        return True
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _host_allowed(host: str, allowed_domains, seed_host: str | None) -> bool:
    domains = tuple(
        item.strip().lower().rstrip(".")
        for item in (allowed_domains or ())
        if item and item.strip()
    )
    if domains:
        return any(host == item or host.endswith("." + item) for item in domains)
    if seed_host:
        return host == seed_host or host.endswith("." + seed_host)
    return True


def validate_target(
    url: str,
    allowed_domains=(),
    seed_host: str | None = None,
    allow_loopback: bool = False,
) -> ValidatedTarget:
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise CrawlError("Malformed URL") from exc
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise CrawlError("Only http and https URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise CrawlError("URL credentials are not allowed")
    try:
        port = parts.port
    except ValueError as exc:
        raise CrawlError("Invalid port") from exc
    if port is None:
        port = 443 if scheme == "https" else 80
    if not 1 <= port <= 65535:
        raise CrawlError("Invalid port")
    host = parts.hostname
    if not host or "%" in host:
        raise CrawlError("Invalid host")
    host = host.lower().rstrip(".")
    if not _host_allowed(host, allowed_domains, seed_host):
        raise CrawlError(f"Host {host} is not allowed")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CrawlError(f"Could not resolve {host}") from exc
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses:
        raise CrawlError(f"Could not resolve {host}")
    for address in addresses:
        if not _is_safe_address(address, allow_loopback):
            raise CrawlError(f"Resolved address {address} is not permitted")
    return ValidatedTarget(scheme=scheme, host=host, port=port, address=addresses[0])


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._pinned_address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_address, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(
        self,
        host: str,
        port: int,
        address: str,
        timeout: float,
        context: ssl.SSLContext | None = None,
    ):
        super().__init__(host, port, timeout=timeout, context=context)
        self._pinned_address = address
        self._ssl_context = context

    def connect(self) -> None:
        self.sock = socket.create_connection((self._pinned_address, self.port), self.timeout)
        context = self._ssl_context or ssl.create_default_context()
        self.sock = context.wrap_socket(self.sock, server_hostname=self.host)


def _connection(target: ValidatedTarget, limits: CrawlLimits):
    if target.scheme == "https":
        return _PinnedHTTPSConnection(
            target.host, target.port, target.address, limits.timeout
        )
    return _PinnedHTTPConnection(target.host, target.port, target.address, limits.timeout)


def _request_target(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return path


def _check_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise CrawlError("Crawl time budget exhausted")


def _read_limited(response, limits: CrawlLimits, deadline: float, cancel) -> bytes:
    declared = response.getheader("Content-Length")
    if declared:
        try:
            if int(declared) > limits.max_response_bytes:
                raise CrawlError("Response exceeds byte limit")
        except ValueError as exc:
            raise CrawlError("Invalid Content-Length") from exc
    chunks: list[bytes] = []
    total = 0
    while True:
        if cancel is not None and cancel():
            raise CrawlError("Crawl cancelled")
        _check_deadline(deadline)
        chunk = response.read(8192)
        if not chunk:
            break
        total += len(chunk)
        if total > limits.max_response_bytes:
            raise CrawlError("Response exceeds byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_body(raw: bytes, response, limits: CrawlLimits) -> str:
    encoding = (response.getheader("Content-Encoding") or "").strip().lower()
    if encoding in ("gzip", "x-gzip"):
        decompressor = zlib.decompressobj(31)
    elif encoding == "deflate":
        decompressor = zlib.decompressobj(15)
    elif encoding in ("", "identity"):
        return raw.decode("utf-8", errors="replace")
    else:
        raise CrawlError(f"Unsupported content encoding {encoding}")
    cap = limits.max_decompressed_bytes
    decoded = decompressor.decompress(raw, cap + 1)
    decoded += decompressor.flush()
    if len(decoded) > cap:
        raise CrawlError("Decompressed response exceeds byte limit")
    return decoded.decode("utf-8", errors="replace")


def fetch(
    url: str,
    limits: CrawlLimits | None = None,
    allowed_domains=(),
    seed_host: str | None = None,
    allow_loopback: bool = False,
    cancel: Callable[[], bool] | None = None,
    deadline: float | None = None,
    redirects: int = 0,
) -> FetchedPage:
    limits = limits or CrawlLimits()
    deadline = deadline if deadline is not None else time.monotonic() + limits.max_time
    target = validate_target(url, allowed_domains, seed_host, allow_loopback)
    if seed_host is None:
        seed_host = target.host
    if cancel is not None and cancel():
        raise CrawlError("Crawl cancelled")
    _check_deadline(deadline)
    connection = _connection(target, limits)
    try:
        connection.request(
            "GET",
            _request_target(url),
            headers={
                "User-Agent": limits.user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        location = response.getheader("Location")
        if 300 <= response.status < 400 and location:
            if redirects >= limits.max_redirects:
                raise CrawlError("Too many redirects")
            response.close()
            next_url = urljoin(url, location)
            return fetch(
                next_url,
                limits,
                allowed_domains,
                seed_host,
                allow_loopback,
                cancel,
                deadline,
                redirects + 1,
            )
        if response.status != 200:
            raise CrawlError(f"HTTP status {response.status}")
        content_type = (response.getheader("Content-Type") or "").split(";", 1)[0].strip().lower()
        if content_type and content_type not in (
            "text/html",
            "application/xhtml+xml",
            "text/plain",
        ):
            raise CrawlError(f"Unsupported content type {content_type}")
        raw = _read_limited(response, limits, deadline, cancel)
        body = _decode_body(raw, response, limits)
        return FetchedPage(
            url=url,
            final_url=url,
            status=response.status,
            content_type=content_type,
            body=body,
        )
    finally:
        connection.close()


def _normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            parts.query,
            "",
        )
    )


def crawl_site(
    url: str,
    config: Config | None = None,
    max_pages: int | None = None,
    max_depth: int | None = None,
    limits: CrawlLimits | None = None,
    allowed_domains=(),
    cancel: Callable[[], bool] | None = None,
    allow_loopback: bool = False,
) -> Iterator[CrawledPage]:
    if limits is None:
        limits = limits_from_config(config, max_pages, max_depth)
    if max_pages is not None:
        limits = CrawlLimits(**{**limits.__dict__, "max_pages": max_pages})
    if max_depth is not None:
        limits = CrawlLimits(**{**limits.__dict__, "max_depth": max_depth})
    deadline = time.monotonic() + limits.max_time
    origin = validate_target(url, allowed_domains, allow_loopback=allow_loopback)
    seed_host = origin.host
    robots = RobotsRules()
    try:
        robots_page = fetch(
            f"{origin.origin}/robots.txt",
            limits,
            allowed_domains,
            seed_host,
            allow_loopback,
            cancel,
            deadline,
        )
        robots = parse_robots(robots_page.body, limits.user_agent)
    except CrawlError:
        pass

    queue: list[tuple[str, int]] = [(url, 0)]
    visited: set[str] = set()
    seen_hashes: set[str] = set()
    crawled = 0
    last_request: float | None = None

    while queue and crawled < limits.max_pages:
        if cancel is not None and cancel():
            return
        _check_deadline(deadline)
        current, depth = queue.pop(0)
        key = _normalize_url(current)
        if key in visited:
            continue
        visited.add(key)
        if not robots.is_allowed(current, limits.user_agent):
            continue
        delay = robots.delay_for(limits.user_agent)
        if last_request is not None and delay:
            remaining = max(0.0, delay - (time.monotonic() - last_request))
            if remaining:
                time.sleep(min(remaining, max(0.0, deadline - time.monotonic())))
        last_request = time.monotonic()
        try:
            page = fetch(
                current,
                limits,
                allowed_domains,
                seed_host,
                allow_loopback,
                cancel,
                deadline,
            )
        except CrawlError:
            continue
        extracted = extract_html(page.body, page.final_url)
        content_hash = hashlib.sha256(extracted.content.encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)
        crawled += 1
        yield CrawledPage(
            url=page.final_url,
            depth=depth,
            title=extracted.title,
            headings=extracted.headings,
            body=extracted.body,
            text=extracted.content,
            links=extracted.links,
            content_hash=content_hash,
        )
        if depth >= limits.max_depth:
            continue
        for link in extracted.links:
            if _normalize_url(link) in visited:
                continue
            try:
                validate_target(link, allowed_domains, seed_host, allow_loopback)
            except CrawlError:
                continue
            queue.append((link, depth + 1))
