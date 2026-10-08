"""End-to-end tests for a Streamlit-free HTTP service and browser application."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import json
import re
import subprocess
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from option_lab.server import DOCS, Handler

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class LocalWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                         partial(Handler, directory=str(DOCS)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def test_http_endpoints_and_static_resources(self):
        for path, mime in (
            ("/", "text/html"), ("/styles.css", "text/css"),
            ("/pricing.mjs", "javascript"), ("/market.js", "javascript"),
            ("/market.css", "text/css")):
            with self.subTest(path=path), urlopen(self.base + path, timeout=15) as res:
                self.assertEqual(res.status, 200)
                self.assertIn(mime, res.headers["Content-Type"])
                self.assertGreater(len(res.read()), 100)
        with urlopen(self.base + "/api/health", timeout=10) as response:
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["market_data"], "local_yfinance")
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.base + "/api/chain?ticker=SPY&expiry=wrong", timeout=10)
        self.assertEqual(cm.exception.code, 400)

    @unittest.skipUnless(CHROME.is_file(), "Headless Chrome not installed")
    def test_real_browser_price_and_mode_detection(self):
        with tempfile.TemporaryDirectory(prefix="optionlab-chrome-") as profile:
            result = subprocess.run([
                str(CHROME), "--headless=new", "--no-first-run",
                "--disable-background-networking", "--disable-gpu",
                "--user-data-dir=" + profile, "--window-size=1440,900",
                "--virtual-time-budget=3500", "--dump-dom", self.base + "/"
            ], text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=65)
        self.assertEqual(result.returncode, 0, result.stderr[-1200:])
        self.assertIn("LOCAL YAHOO DATA ADAPTER READY", result.stdout)
        for key in ("call", "put", "dc", "dp"):
            match = re.search('id="' + key + r'"[^>]*>([^<]+)', result.stdout)
            self.assertIsNotNone(match, "Missing " + key)
            self.assertNotIn(match.group(1).strip(), ("", "—", "n/a"))


if __name__ == "__main__":
    unittest.main()
