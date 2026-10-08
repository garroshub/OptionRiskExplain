"""CLI entry point for the Streamlit-free options toolkit."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .market import MarketDataError, expirations, option_chain, quote
from .pricing import price_european
from .risk import explain_csv
from .server import serve


def make_parser():
    parser = argparse.ArgumentParser(prog="option-lab", description="Equity option P&L explain, pricing, option chains and local reporting.")
    cmd = parser.add_subparsers(dest="command", required=True)
    p = cmd.add_parser("price", help="Black-Scholes European call/put and Greeks")
    p.add_argument("--spot", type=float, required=True)
    p.add_argument("--strike", type=float, required=True)
    p.add_argument("--days", type=float, default=30)
    p.add_argument("--rate", type=float, default=5, help="Risk-free rate in percent")
    p.add_argument("--dividend", type=float, default=0, help="Dividend yield in percent")
    p.add_argument("--volatility", type=float, default=25, help="Annualized volatility in percent")
    for name in ("quote", "expirations", "chain"):
        sub = cmd.add_parser(name)
        sub.add_argument("ticker")
        if name == "chain":
            sub.add_argument("--expiry", required=True)
            sub.add_argument("--side", choices=("both", "calls", "puts"), default="both")
    web = cmd.add_parser("serve", help="Local browser tool + Yahoo Finance API")
    web.add_argument("--port", type=int, default=8765)
    report = cmd.add_parser("explain", help="Reconcile P&L on unchanged option positions from two CSV snapshots")
    report.add_argument("--start", required=True, help="Start-of-period CSV")
    report.add_argument("--end", required=True, help="End-of-period CSV")
    report.add_argument("--threshold", type=float, default=500.0, help="User-defined exception threshold in USD (not regulatory)")
    report.add_argument("--output", help="Write full report as JSON")
    report.add_argument("--csv-output", help="Write per-contract attribution as CSV")
    return parser


def main(argv=None) -> int:
    args = make_parser().parse_args(argv)
    try:
        if args.command == "price":
            result = price_european(args.spot, args.strike, args.days / 365,
                                    args.rate / 100, args.dividend / 100,
                                    args.volatility / 100)
        elif args.command == "quote":
            result = quote(args.ticker)
        elif args.command == "expirations":
            result = expirations(args.ticker)
        elif args.command == "chain":
            result = option_chain(args.ticker, args.expiry, args.side)
        elif args.command == "explain":
            result = explain_csv(Path(args.start).read_text(encoding="utf-8-sig"),
                                 Path(args.end).read_text(encoding="utf-8-sig"),
                                 args.threshold)
            if args.output:
                Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            if args.csv_output:
                fields = ("contract","quantity","observed_pnl","delta","gamma",
                          "vega","theta","rho","dividend","approximation_residual",
                          "market_basis_change","unexplained_pnl","flags")
                with Path(args.csv_output).open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    for position in result["positions"]:
                        writer.writerow({**position, "flags": "|".join(position["flags"])})
        elif args.command == "serve":
            serve(port=args.port)
            return 0
        if args.command == "explain" and args.output:
            print(json.dumps({"report_written": args.output,
                              "positions": result["position_count"],
                              "observed_pnl": result["totals"]["observed_pnl"],
                              "exception_count": result["exception_count"]}, indent=2))
        else:
            print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, MarketDataError, OSError) as exc:
        make_parser().exit(2, "Error: " + str(exc) + "\n")
    except KeyboardInterrupt:
        return 130
    return 1
