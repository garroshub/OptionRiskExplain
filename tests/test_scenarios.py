"""Scenario reproducibility and zero-backend browser experience."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest import TestCase
import unittest

from option_lab.risk import explain_csv

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class ScenarioFixtureTests(TestCase):
    def test_all_published_scenarios_exactly_recompute_with_python_engine(self):
        data = json.loads((DOCS / "risk-scenarios.json").read_text(encoding="utf-8"))
        cases = data["scenarios"]
        self.assertEqual(len(cases), 4)
        self.assertEqual({x["id"] for x in cases},
                         {"desk-review","equity-selloff","volatility-spike","valuation-break"})
        for case in cases:
            report = explain_csv(case["start_csv"],case["end_csv"],500)
            self.assertEqual(report,case["report"],case["id"])
            self.assertAlmostEqual(report["totals"]["reconciliation_error"],0,places=6)
            self.assertEqual(report["position_count"],5)
        cases = {item["id"]:item for item in cases}
        self.assertLess(cases["equity-selloff"]["report"]["totals"]["observed_pnl"],-10000)
        self.assertGreater(cases["volatility-spike"]["report"]["totals"]["vega"],10000)
        self.assertEqual(cases["volatility-spike"]["report"]["totals"]["delta"],0)
        self.assertGreater(cases["valuation-break"]["report"]["exception_count"],0)


@unittest.skipUnless(sync_playwright is not None and CHROME.is_file(),
                     "Playwright and Chrome needed for static and mobile demo")
class BrowserStaticScenarios(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd=ThreadingHTTPServer(("127.0.0.1",0),partial(
            SimpleHTTPRequestHandler,directory=str(DOCS)))
        cls.thread=Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()
        cls.url=f"http://127.0.0.1:{cls.httpd.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(2)

    def test_static_browser_scenario_switch_without_python_api(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=str(CHROME),headless=True)
            try:
                for width,height in ((1440,900),(390,844)):
                    page=browser.new_page(viewport={"width":width,"height":height})
                    errors=[]
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    page.goto(self.url,wait_until="networkidle")
                    self.assertTrue(page.locator(".hero-btn-primary").first.is_visible())
                    self.assertIn("Option Risk Explain",page.locator("h1").inner_text())
                    self.assertFalse(page.locator("#risk-report").is_hidden())
                    self.assertIn("SYNTHETIC DATA",page.locator("#risk-mode").inner_text())
                    self.assertIn("Scenario results available",page.locator("#risk-local").text_content())
                    self.assertTrue(page.locator("#risk-run").is_disabled())
                    first=page.locator("#risk-pnl").inner_text()
                    for opt in ("equity-selloff","volatility-spike","valuation-break","desk-review"):
                        page.locator("#risk-scenario").select_option(opt)
                        self.assertEqual(page.locator("#risk-scenario").input_value(),opt)
                        self.assertEqual(page.locator("#risk-reconcile").inner_text(),"$0.000000")
                    self.assertEqual(page.locator("#risk-pnl").inner_text(),first)
                    self.assertFalse(errors,errors)
                    overflow = page.evaluate(
                        "() => document.documentElement.scrollWidth > window.innerWidth + 2")
                    self.assertFalse(overflow, f"{width}px viewport has horizontal overflow")
                    self.assertFalse(page.locator("#risk-advanced").evaluate("(x)=>x.open"))
                    if width==1440:
                        self.assertLess(page.locator("#risk-scenario").bounding_box()["y"], 650)
                        self.assertLess(page.locator("#risk-pnl").bounding_box()["y"], 900)
                    page.close()
            finally:
                browser.close()
