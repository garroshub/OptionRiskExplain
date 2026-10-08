"""Streamlit-independent tests of package, HTTP routing and mocked Yahoo adapter."""
import json
import math
from unittest import TestCase, mock
from types import SimpleNamespace
import unittest

from option_lab import price_european
from option_lab import market
from option_lab.server import respond


class PricingTests(TestCase):
    def test_textbook(self):
        p = price_european(100, 100, 1, .05, 0, .2)
        self.assertAlmostEqual(p["call"], 10.450583572185565, places=8)
        self.assertAlmostEqual(p["put"], 5.573526022256971, places=8)
        self.assertAlmostEqual(p["gamma"], .018762017345846895, places=9)

    def test_parity(self):
        p = price_european(110, 95, .6, .04, .025, .31)
        self.assertAlmostEqual(p["call"] - p["put"],
                               110 * math.exp(-.025 * .6) - 95 * math.exp(-.04 * .6), places=10)

    def test_zero_vol_and_expiry(self):
        self.assertEqual(price_european(112,100,0,.05,.0,.2)["call"], 12)
        self.assertIsNone(price_european(112,100,0,.05,.0,.2)["gamma"])
        self.assertAlmostEqual(price_european(100,100,1,.05,0,0)["call"],
                               100 - 100*math.exp(-.05))

    def test_bad_inputs(self):
        with self.assertRaises(ValueError):
            price_european(100, 0, 1, .03)
        with self.assertRaises(ValueError):
            price_european(float("nan"), 100, 1, .03)


class AdapterTests(TestCase):
    def test_validation(self):
        self.assertEqual(market.validate_symbol("spy"), "SPY")
        with self.assertRaises(ValueError):
            market.validate_symbol("../../config")
        status, content = respond("/api/chain?ticker=SPY&expiry=bad")
        self.assertEqual(status, 400)
        self.assertIn("error", content)

    def test_quote_mock(self):
        fake = SimpleNamespace(fast_info={"lastPrice": 123.45}, info={"trailingAnnualDividendYield": .01})
        with mock.patch.object(market, "_ticker", return_value=fake):
            result = market.quote("spy")
        self.assertEqual(result["last_price"], 123.45)
        self.assertEqual(result["ticker"], "SPY")

    def test_option_chain_mock(self):
        import pandas as pd
        frame = pd.DataFrame([{"strike": 100.0, "bid": float("nan"),
                               "ask": 2.5, "lastTradeDate": pd.Timestamp("2026-10-07T12:00Z")}])
        fake = SimpleNamespace(options=("2026-10-09",),
                               option_chain=lambda expiry: SimpleNamespace(calls=frame, puts=frame))
        with mock.patch.object(market, "_ticker", return_value=fake):
            result = market.option_chain("SPY", "2026-10-09")
        self.assertEqual(result["calls_count"], 1)
        self.assertIsNone(result["calls"][0]["bid"])
        json.dumps(result, allow_nan=False)

    def test_health(self):
        status, result = respond("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])


if __name__ == "__main__":
    unittest.main()
