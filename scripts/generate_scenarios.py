"""Generate four synthetic portfolio P&L attribution cases."""
from __future__ import annotations

import csv
from copy import deepcopy
from datetime import date
from io import StringIO
import json
from pathlib import Path

from option_lab import explain_csv, price_european

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "examples"
DOCS = ROOT / "docs"
DATE0, DATE1 = "2026-10-05", "2026-10-06"
COLUMNS = ("as_of","underlying","option_type","expiry","strike","quantity",
           "multiplier","spot","mark","volatility","rate","dividend_yield",
           "bid","ask","source")


def to_csv(rows: list[dict]) -> str:
    out = StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in COLUMNS})
    return out.getvalue()


def get_model_mark(row: dict) -> float:
    dte = (date.fromisoformat(row["expiry"]) -
           date.fromisoformat(row["as_of"])).days
    return round(price_european(
        float(row["spot"]), float(row["strike"]), dte / 365.0,
        float(row["rate"]), float(row["dividend_yield"]),
        float(row["volatility"]))[row["option_type"]], 2)


def scenario(scenario_id: str, name: str, label: str, question: str,
             market_move: str, focus: str, spot1: dict | None,
             vol_step: dict | None, basis: dict | None = None,
             crossed: bool = False, baseline: bool = False) -> dict:
    source = (INPUT / f"positions_{DATE0}.csv").read_text(encoding="utf-8")
    starts = list(csv.DictReader(StringIO(source)))
    if baseline:
        ends = list(csv.DictReader(
            StringIO((INPUT / f"positions_{DATE1}.csv").read_text(encoding="utf-8"))))
    else:
        ends = deepcopy(starts)
        for row in ends:
            sym = row["underlying"]
            key = (sym, row["option_type"], float(row["strike"]))
            row["as_of"] = DATE1
            row["spot"] = spot1[sym]
            row["volatility"] = round(float(row["volatility"]) +
                                      vol_step[sym], 5)
            row["rate"] = .040
            mark = max(.01, get_model_mark(row) + (basis or {}).get(key, 0.0))
            row["mark"] = round(mark, 2)
            row["bid"] = round(max(0, row["mark"] - .12), 2)
            row["ask"] = round(row["mark"] + .12, 2)
            row["source"] = "SYNTHETIC_SCENARIO"
        if crossed:
            for row in ends:
                if row["underlying"] == "AAPL" and row["option_type"] == "put":
                    row["bid"] = round(float(row["mark"]) + .45,2)
                    row["ask"] = round(float(row["mark"]) + .25,2)
    for row in starts:
        row["source"] = "SYNTHETIC_SCENARIO"
    start_csv, end_csv = to_csv(starts), to_csv(ends)
    report = explain_csv(start_csv, end_csv, exception_threshold=500.0)
    if abs(report["totals"]["reconciliation_error"]) > 1e-7:
        raise ArithmeticError("Scenario failed to reconcile: " + scenario_id)
    return {
        "id": scenario_id, "name": name, "label": label, "question": question,
        "market_move": market_move, "focus": focus,
        "start_csv": start_csv, "end_csv": end_csv, "report": report,
    }


def main():
    items = [
        scenario(
            "desk-review", "Daily desk review", "Mixed exposures",
            "Which factors explain the daily change?",
            "SPY -0.9%, AAPL +1.2%. Small IV changes.",
            "Model basis and quote-quality checks",
            None, None, baseline=True
        ),
        scenario(
            "equity-selloff", "Equity market selloff", "Delta and Gamma",
            "How do falling stock prices and higher IV affect P&L?",
            "SPY -5.5%, AAPL -6.0%. IV rises 5 to 6 points.",
            "Delta, Gamma and higher-order pricing effects",
            {"SPY": 520, "AAPL": 235}, {"SPY": .05, "AAPL": .06}
        ),
        scenario(
            "volatility-spike", "Volatility repricing", "Vega",
            "How much of the daily P&L comes from higher IV?",
            "Spot prices unchanged. IV rises 8 points.",
            "Vega and non-linear volatility effects",
            {"SPY": 550, "AAPL": 250}, {"SPY": .08, "AAPL": .08}
        ),
        scenario(
            "valuation-break", "Valuation exception", "Quote controls",
            "Which marks differ from the model reference?",
            "SPY +0.2%, AAPL -0.4%. IV nearly unchanged.",
            "Mark/model differences and a crossed quote",
            {"SPY": 551, "AAPL": 249}, {"SPY": .002, "AAPL": .003},
            {("SPY","call",550.0): 2.5, ("AAPL","call",255.0): -1.2},
            crossed=True
        )
    ]
    DOCS.mkdir(exist_ok=True)
    content = {"schema_version":1, "data_label":"SYNTHETIC, NOT MARKET DATA",
               "scenarios":items}
    (DOCS / "risk-scenarios.json").write_text(
        json.dumps(content, indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    for item in items:
        report = item["report"]
        print(item["id"], "observed",round(report["totals"]["observed_pnl"],2),
              "delta",round(report["totals"]["delta"],2),
              "vega",round(report["totals"]["vega"],2),
              "residual",round(report["totals"]["approximation_residual"],2),
              "exceptions",report["exception_count"])
    print("BUILT", len(items), "scenarios")


if __name__ == "__main__":
    main()
