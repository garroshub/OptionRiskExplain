"""Full Chrome interaction: synthetic preview, CSV upload, risk exports and error handling."""
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest import TestCase
import unittest

from option_lab.server import Handler, DOCS

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

REPO = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

@unittest.skipUnless(sync_playwright is not None and CHROME.is_file(),
                     "Playwright and Chrome required for browser risk test")
class BrowserRiskTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),partial(Handler,directory=str(DOCS)))
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def test_risk_flow(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=str(CHROME),headless=True,
                                      args=["--no-first-run","--disable-gpu"])
            try:
                page=browser.new_page(viewport={"width":1440,"height":1000},accept_downloads=True)
                errors=[]
                page.on("pageerror",lambda exception: errors.append(str(exception)))
                page.goto(self.url,wait_until="networkidle")
                self.assertIn("SYNTHETIC DATA",page.locator("#risk-mode").inner_text())
                self.assertEqual(page.locator("#risk-count").inner_text(),"5")
                self.assertLess(page.locator("#risk-scenario").bounding_box()["y"],650)
                self.assertLess(page.locator("#risk-pnl").bounding_box()["y"],930)
                original=page.locator("#risk-pnl").inner_text()
                page.locator("#risk-scenario").select_option("equity-selloff")
                selloff=page.locator("#risk-pnl").inner_text()
                self.assertNotEqual(original,selloff)
                self.assertIn("Delta",page.locator("#risk-scenario-focus").inner_text())
                page.locator("#risk-scenario").select_option("volatility-spike")
                self.assertNotEqual(selloff,page.locator("#risk-pnl").inner_text())
                self.assertEqual(page.locator("#risk-exceptions").inner_text(),"0")
                self.assertIn("VEGA",page.locator("#risk-scenario-label").inner_text())
                page.locator("#risk-scenario").select_option("valuation-break")
                self.assertGreater(int(page.locator("#risk-exceptions").inner_text()),0)
                self.assertIn("CROSSED QUOTE",page.locator("#risk-exception-rows").inner_text())
                page.locator("#risk-scenario").select_option("desk-review")
                self.assertIn("Local Python server connected",page.locator("#risk-local").text_content())
                page.locator("#risk-advanced summary").click()
                page.locator("#risk-start").set_input_files(str(REPO/"examples"/"positions_2026-10-05.csv"))
                page.locator("#risk-end").set_input_files(str(REPO/"examples"/"positions_2026-10-06.csv"))
                page.locator("#risk-run").click()
                self.assertIn("USER DATA",page.locator("#risk-mode").inner_text())
                self.assertEqual(page.locator("#risk-rows tr").count(),5)
                self.assertEqual(page.locator("#risk-bars .risk-bar-row").count(),8)
                self.assertEqual(page.locator("#risk-reconcile").inner_text(),"$0.000000")
                with page.expect_download() as pending:
                    page.locator("#risk-json").click()
                self.assertEqual(pending.value.suggested_filename,"option-risk-explain.json")
                with page.expect_download() as pending:
                    page.locator("#risk-csv").click()
                self.assertEqual(pending.value.suggested_filename,"option-risk-explain-positions.csv")
                page.locator("#risk").scroll_into_view_if_needed()
                page.screenshot(path=str(REPO/"assets"/"readme"/"risk-showcase.png"))
                self.assertFalse(errors,errors)
                page.locator("#risk-threshold").fill("-5")
                self.assertFalse(page.locator("#risk-form").evaluate("(form)=>form.checkValidity()"))
                page.locator("#risk-demo").click()
                self.assertIn("SYNTHETIC DATA",page.locator("#risk-mode").inner_text())
                self.assertIn("$",page.locator("#risk-pnl").inner_text())
            finally:
                browser.close()
