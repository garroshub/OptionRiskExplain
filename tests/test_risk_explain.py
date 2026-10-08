"""Fixed-book P&L attribution: reconciliation, signed positions and safeguards."""
import math
from unittest import TestCase
from option_lab import price_european, explain_portfolio
from option_lab.risk import explain_csv

def base(when="2026-10-05", side="call", qty=10, spot=100, mark=5,
         volatility=.25, rate=.04, div=.01):
    return dict(as_of=when, underlying="SPY", option_type=side,
                expiry="2026-11-20", strike=100, quantity=qty, multiplier=100,
                spot=spot, mark=mark, volatility=volatility, rate=rate,
                dividend_yield=div, source="synthetic-test")

class AttributionTests(TestCase):
    def test_model_only_pnl_reconciles_exactly(self):
        a=base(); b=base("2026-10-06",spot=101,volatility=.26)
        for x in (a,b):
            from datetime import date
            years=(date.fromisoformat(x["expiry"])-date.fromisoformat(x["as_of"])).days/365
            x["mark"]=price_european(x["spot"],x["strike"],years,x["rate"],x["dividend_yield"],x["volatility"])["call"]
        r=explain_portfolio([a],[b],1)
        t=r["totals"]
        self.assertAlmostEqual(t["observed_pnl"],t["model_pnl"],places=8)
        self.assertAlmostEqual(t["market_basis_change"],0,places=8)
        self.assertAlmostEqual(t["observed_pnl"],sum(t[k] for k in
            ("delta","gamma","vega","theta","rho","dividend","approximation_residual","market_basis_change")),places=7)
        self.assertAlmostEqual(t["delta"],r["positions"][0]["delta"])
        self.assertTrue(math.isfinite(t["approximation_residual"]))

    def test_short_pnl_and_basis_change(self):
        a=base(qty=-3,mark=6)
        b=base("2026-10-06",qty=-3,mark=7)
        r=explain_portfolio([a],[b],100)
        self.assertEqual(r["totals"]["observed_pnl"],-300)
        self.assertAlmostEqual(r["totals"]["reconciliation_error"],0)
        self.assertTrue(any(x["code"]=="MARKET_MODEL_BASIS_CHANGE" for x in r["exceptions"]))

    def test_changed_book_rejected(self):
        a=base()
        b=base("2026-10-06",qty=9)
        with self.assertRaisesRegex(ValueError,"quantity"):
            explain_portfolio([a],[b])
        b=base("2026-10-06");b["strike"]=105
        with self.assertRaisesRegex(ValueError,"Contract universe"):
            explain_portfolio([a],[b])

    def test_snapshot_quality(self):
        a=base();b=base("2026-10-06")
        with self.assertRaisesRegex(ValueError,"same as_of"):
            explain_portfolio([a,dict(a,underlying="AAPL",as_of="2026-10-04")],[b])
        with self.assertRaisesRegex(ValueError,"duplicate"):
            explain_portfolio([a,a],[b])
        with self.assertRaisesRegex(ValueError,"inconsistent underlying spot"):
            explain_portfolio([a,dict(a,option_type="put",spot=105)],[b])
        with self.assertRaisesRegex(ValueError,"decimal fractions"):
            explain_portfolio([dict(a,volatility=25)],[b])
        with self.assertRaisesRegex(ValueError,"after start"):
            explain_portfolio([b],[a])
        with self.assertRaisesRegex(ValueError,"finite"):
            explain_portfolio([dict(a,mark=float("nan"))],[b])
        with self.assertRaisesRegex(ValueError,"expiry"):
            explain_portfolio([dict(a,expiry="2026-10-05")],[b])

    def test_quote_flags_and_threshold(self):
        a=base(mark=10);b=base("2026-10-06",mark=10)
        a.update(bid=11,ask=12)
        b.update(bid=13,ask=12)
        r=explain_portfolio([a],[b],0)
        self.assertIn("START_MARK_OUTSIDE_SPREAD",r["positions"][0]["flags"])
        self.assertIn("END_CROSSED_QUOTE",r["positions"][0]["flags"])

    def test_csv_validation(self):
        with self.assertRaisesRegex(ValueError,"missing required"):
            explain_csv("foo,bar\n1,2", "foo,bar\n1,2")
        with self.assertRaisesRegex(ValueError,"nonnegative"):
            explain_portfolio([base()],[base("2026-10-06")],-1)

    def test_dividend_yield_isolated_effect(self):
        a=base();b=base("2026-10-06",div=.02)
        r=explain_portfolio([a],[b])
        self.assertNotEqual(r["totals"]["dividend"],0.0)
        self.assertAlmostEqual(r["totals"]["reconciliation_error"],0.0,places=8)
