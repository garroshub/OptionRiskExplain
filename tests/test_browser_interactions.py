"""Playwright integration test for all interactive Streamlit-free browser features.

Uses mocked Yahoo responses so the browser test is stable when Yahoo limits access.
The separate live CLI test validates real upstream connectivity.
"""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest import TestCase, mock
import unittest

from option_lab import market
from option_lab.server import DOCS, Handler

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


@unittest.skipUnless(sync_playwright is not None and CHROME.is_file(),
                     "Playwright and desktop Chrome required")
class BrowserInteractionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0),
                                        partial(Handler, directory=str(DOCS)))
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(2)

    def test_pricing_and_option_chain_workflow(self):
        quote = {
            "ticker": "SPY", "last_price": 111.25,
            "trailing_annual_dividend_yield": .013,
            "retrieved_at": "2026-10-07T10:00:00+00:00"
        }
        expiry = {
            "ticker": "SPY", "expirations": ["2026-10-09", "2026-10-16"],
            "retrieved_at": "2026-10-07T10:00:00+00:00"
        }
        row = {
            "strike": 110.0, "lastPrice": 2.8, "bid": 2.7,
            "ask": 2.9, "impliedVolatility": .25,
            "volume": 150, "openInterest": 500
        }
        chain = {
            "calls": [row], "puts": [dict(row, strike=112.0)],
            "calls_count": 1, "puts_count": 1,
            "retrieved_at": "2026-10-07T10:00:00+00:00"
        }
        with mock.patch.object(market, "quote", return_value=quote), \
             mock.patch.object(market, "expirations", return_value=expiry), \
             mock.patch.object(market, "option_chain", return_value=chain):
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=str(CHROME), headless=True,
                    args=["--no-first-run", "--disable-gpu"])
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 900})
                    page.goto(self.url, wait_until="networkidle")
                    self.assertEqual(page.locator("#call").inner_text(), "$3.0626")
                    self.assertIn("LOCAL YAHOO DATA ADAPTER READY", page.locator("#market-status").inner_text())
                    page.locator("#S").fill("110")
                    page.locator("#S").press("Tab")
                    self.assertNotEqual(page.locator("#call").inner_text(), "$3.0626")
                    page.locator("#ticker-button").click()
                    self.assertIn("$111.25", page.locator("#market-quote").inner_text())
                    self.assertEqual(page.locator("#market-expiry option").count(), 2)
                    page.locator("#market-expiry").select_option("2026-10-16")
                    page.locator("#chain-button").click()
                    self.assertIn("110.00", page.locator("#calls-rows").inner_text())
                    self.assertIn("112.00", page.locator("#puts-rows").inner_text())
                    self.assertIn("25.00%", page.locator("#calls-rows").inner_text())
                    page.locator("#market-transfer").click()
                    self.assertEqual(page.locator("#S").input_value(), "111.25")
                    self.assertEqual(page.locator("#q").input_value(), "1.3000")
                finally:
                    browser.close()


if __name__ == "__main__":
    unittest.main()
