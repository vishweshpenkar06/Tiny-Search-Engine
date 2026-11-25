import gzip
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from config import Config
from crawler.crawl import CrawlError, CrawlLimits, crawl_site, fetch, validate_target
from crawler.extract import extract_html
from crawler.robots import parse_robots


class CrawlHandler(BaseHTTPRequestHandler):
    robots_delay = "0"
    port = 0

    def log_message(self, format, *args):
        return

    def _send(self, status, body, content_type="text/html; charset=utf-8", headers=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/robots.txt":
            self._send(
                200,
                f"User-agent: *\nDisallow: /private\nAllow: /\nCrawl-delay: {self.robots_delay}\n",
                "text/plain; charset=utf-8",
            )
        elif path == "/":
            self._send(
                200,
                "<html><head><title>Home</title></head><body><h1>Welcome page</h1>"
                '<a href="/a">Alpha</a><a href="/private">Private</a>'
                '<a href="/deep/one">Deep</a><a href="/redirect">Redirect</a>'
                "</body></html>",
            )
        elif path == "/a":
            self._send(
                200,
                "<html><head><title>Alpha page</title></head><body><p>Alpha body text</p>"
                '<a href="/deep/two">Deeper</a></body></html>',
            )
        elif path == "/private":
            self._send(200, "<html><title>Secret</title><body>private content</body></html>")
        elif path in ("/deep/one", "/deep/two"):
            self._send(200, f"<html><title>{path}</title><body>deep page {path}</body></html>")
        elif path == "/external":
            self._send(
                200,
                "<html><title>External links</title><body>"
                f'<a href="http://localhost:{self.port}/">localhost</a>'
                '<a href="/a">alpha</a></body></html>',
            )
        elif path == "/redirect":
            self._redirect("/a")
        elif path == "/loop":
            self._redirect("/loop")
        elif path == "/to-private":
            self._redirect("http://10.0.0.1/")
        elif path == "/big":
            self._send(200, b"x" * 20000)
        elif path == "/gzip":
            payload = gzip.compress(b"<html><title>Zipped</title><body>compressed body here</body></html>")
            self._send(200, payload, "text/html; charset=utf-8", {"Content-Encoding": "gzip"})
        else:
            self._send(404, "<html><body>missing</body></html>")


class CrawlerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), CrawlHandler)
        CrawlHandler.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{CrawlHandler.port}"
        root = Path(tempfile.mkdtemp())
        cls.config = Config(
            debug=False,
            host="127.0.0.1",
            port=5000,
            data_dir=root,
            upload_dir=root / "uploads",
            db_path=root / "index.db",
            model_dir=root / "models",
            max_content_length=1024 * 1024,
            max_file_size=1024 * 1024,
            max_files=100,
            max_query_length=500,
            admin_username=None,
            admin_password_hash=None,
            public_origin=None,
            rate_limit_per_minute=120,
            embeddings_enabled=False,
            crawler_enabled=True,
            crawler_allowed_domains=(),
            bm25_k1=1.2,
            bm25_b=0.75,
            rrf_k=60,
        )
        cls.limits = CrawlLimits(timeout=3.0, max_time=10.0)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_robots_rules_and_crawl_delay(self):
        rules = parse_robots(
            "User-agent: *\nDisallow: /private\nAllow: /public/page\nCrawl-delay: 1.5\n",
            "*",
        )
        self.assertFalse(rules.is_allowed("https://example.test/private"))
        self.assertTrue(rules.is_allowed("https://example.test/public/page"))
        self.assertTrue(rules.is_allowed("https://example.test/other"))
        self.assertEqual(rules.delay_for(), 1.5)
        named = parse_robots(
            "User-agent: *\nDisallow: /\n\nUser-agent: TinySearchBot\nAllow: /private\nDisallow: /\n",
            "TinySearchBot/1.0",
        )
        self.assertTrue(named.is_allowed("https://example.test/private"))
        self.assertFalse(named.is_allowed("https://example.test/a"))

    def test_extract_title_headings_body_and_links(self):
        html = (
            "<html><head><title>Hello &amp; World</title><style>.x{}</style></head>"
            "<body><h1>Heading One</h1><p>Body <b>text</b></p><script>bad()</script>"
            '<a href="/one">one</a><a href="https://other.test/two#frag">two</a>'
            '<a href="#here">local</a><a href="mailto:x@y.test">mail</a></body></html>'
        )
        page = extract_html(html, "https://example.test/base")
        self.assertEqual(page.title, "Hello & World")
        self.assertEqual(page.headings, ("Heading One",))
        self.assertIn("Body text", page.body)
        self.assertNotIn("bad()", page.body)
        self.assertEqual(
            page.links,
            ("https://example.test/one", "https://other.test/two"),
        )
        self.assertIn("Heading One", page.content)

    def test_ssrf_guard_blocks_private_and_special_addresses(self):
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.1/",
            "http://169.254.169.254/",
            "http://[::1]/",
            "http://[::ffff:127.0.0.1]/",
        ):
            with self.assertRaises(CrawlError, msg=url):
                validate_target(url)
        self.assertEqual(validate_target("http://127.0.0.1:9/", allow_loopback=True).address, "127.0.0.1")
        for url in (
            "ftp://example.test/",
            "http://user:pass@example.test/",
            "http://127.0.0.1:0/",
        ):
            with self.assertRaises(CrawlError, msg=url):
                validate_target(url, allow_loopback=True)

    def test_fetch_redirects_byte_caps_and_gzip(self):
        page = fetch(f"{self.base}/redirect", self.limits, allow_loopback=True)
        self.assertEqual(page.final_url, f"{self.base}/a")
        self.assertIn("Alpha body text", page.body)
        with self.assertRaises(CrawlError):
            fetch(f"{self.base}/loop", replace(self.limits, max_redirects=1), allow_loopback=True)
        with self.assertRaises(CrawlError):
            fetch(f"{self.base}/big", replace(self.limits, max_response_bytes=100), allow_loopback=True)
        zipped = fetch(f"{self.base}/gzip", self.limits, allow_loopback=True)
        self.assertIn("compressed body here", zipped.body)
        with self.assertRaises(CrawlError):
            fetch(
                f"{self.base}/gzip",
                replace(self.limits, max_decompressed_bytes=20),
                allow_loopback=True,
            )

    def test_every_redirect_target_is_revalidated(self):
        with self.assertRaises(CrawlError):
            fetch(f"{self.base}/to-private", self.limits, allow_loopback=True)

    def test_crawl_respects_robots_depth_and_page_limits(self):
        urls = [
            page.url
            for page in crawl_site(
                f"{self.base}/",
                self.config,
                max_pages=3,
                max_depth=1,
                limits=self.limits,
                allow_loopback=True,
            )
        ]
        self.assertLessEqual(len(urls), 3)
        self.assertIn(f"{self.base}/", urls)
        self.assertNotIn(f"{self.base}/private", urls)
        self.assertNotIn(f"{self.base}/deep/two", urls)

    def test_crawl_enforces_same_domain(self):
        urls = [
            page.url
            for page in crawl_site(
                f"{self.base}/external",
                self.config,
                max_pages=10,
                max_depth=3,
                limits=self.limits,
                allow_loopback=True,
            )
        ]
        self.assertEqual(urls[0], f"{self.base}/external")
        self.assertTrue(all(urlsplit(url).hostname != "localhost" for url in urls))
        self.assertNotIn(f"http://localhost:{CrawlHandler.port}/", urls)

    def test_crawl_cancellation(self):
        state = {"calls": 0}

        def cancel():
            state["calls"] += 1
            return state["calls"] > 3

        pages = list(
            crawl_site(
                f"{self.base}/",
                self.config,
                max_pages=10,
                max_depth=2,
                limits=self.limits,
                allow_loopback=True,
                cancel=cancel,
            )
        )
        self.assertLessEqual(len(pages), 2)

    def test_crawl_delay_is_respected(self):
        CrawlHandler.robots_delay = "0.1"
        try:
            started = time.monotonic()
            pages = list(
                crawl_site(
                    f"{self.base}/",
                    self.config,
                    max_pages=3,
                    max_depth=1,
                    limits=self.limits,
                    allow_loopback=True,
                )
            )
            elapsed = time.monotonic() - started
        finally:
            CrawlHandler.robots_delay = "0"
        self.assertGreaterEqual(len(pages), 2)
        self.assertGreaterEqual(elapsed, 0.08)


if __name__ == "__main__":
    unittest.main()
