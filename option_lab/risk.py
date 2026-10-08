"""P&L attribution for a fixed equity-option book across two dates.

Option marks are per share. Quantities are signed contracts.
Rates and volatility are decimal annual rates.
"""
from __future__ import annotations

import csv
from datetime import date
import io
from math import isfinite
import re
from typing import Any

from .pricing import price_european

FIELDS = ("as_of", "underlying", "option_type", "expiry", "strike",
          "quantity", "multiplier", "spot", "mark", "volatility", "rate",
          "dividend_yield")
DRIVERS = ("delta", "gamma", "vega", "theta", "rho", "dividend")
COMPONENTS = DRIVERS + ("approximation_residual", "market_basis_change")


def _number(row: dict, name: str, label: str) -> float:
    value = row.get(name)
    if value is None or str(value).strip() == "":
        raise ValueError(f"{label}: missing {name}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}: invalid numeric {name}") from exc
    if not isfinite(result):
        raise ValueError(f"{label}: {name} must be finite")
    return result


def _day(value: Any, label: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        raise ValueError(f"{label}: date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"{label}: date must be YYYY-MM-DD") from exc


def _read_snapshot(rows: list[dict], label: str) -> tuple[date, dict]:
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        raise ValueError(f"{label}: provide 1 to 10,000 position rows")
    snapshot = {}
    dates = set()
    underlying_spots = {}
    for i, raw in enumerate(rows, 1):
        prefix = f"{label} row {i}"
        if not isinstance(raw, dict):
            raise ValueError(f"{prefix}: expected a dictionary")
        row = dict(raw)
        for field in FIELDS:
            if field not in row or row[field] is None or str(row[field]).strip() == "":
                raise ValueError(f"{prefix}: missing {field}")
        row["as_of"] = _day(row["as_of"], prefix)
        row["expiry"] = _day(row["expiry"], prefix)
        dates.add(row["as_of"])
        row["underlying"] = str(row["underlying"]).strip().upper()
        row["option_type"] = str(row["option_type"]).strip().lower()
        if not row["underlying"] or row["option_type"] not in ("call", "put"):
            raise ValueError(f"{prefix}: invalid underlying or option_type (call/put)")
        for field in ("strike", "quantity", "multiplier", "spot", "mark",
                      "volatility", "rate", "dividend_yield"):
            row[field] = _number(row, field, prefix)
        if row["strike"] <= 0 or row["spot"] <= 0 or row["mark"] < 0:
            raise ValueError(f"{prefix}: strike and spot must be positive; mark nonnegative")
        if (row["underlying"] in underlying_spots and
                abs(underlying_spots[row["underlying"]] - row["spot"]) >
                1e-8 * max(1.0, row["spot"])):
            raise ValueError(f"{prefix}: inconsistent underlying spot within snapshot")
        underlying_spots[row["underlying"]] = row["spot"]
        if not (0 <= row["volatility"] <= 5) or abs(row["rate"]) > 1 or abs(row["dividend_yield"]) > 1:
            raise ValueError(f"{prefix}: volatility/rate/dividend_yield must be decimal fractions")
        if (not row["quantity"].is_integer() or row["quantity"] == 0 or
                not row["multiplier"].is_integer() or row["multiplier"] <= 0):
            raise ValueError(f"{prefix}: quantity must be a nonzero signed integer and multiplier a positive integer")
        row["quantity"], row["multiplier"] = int(row["quantity"]), int(row["multiplier"])
        if row["expiry"] < row["as_of"]:
            raise ValueError(f"{prefix}: expired contracts require separate lifecycle treatment")
        for name in ("bid", "ask"):
            if row.get(name) is not None and str(row[name]).strip() != "":
                row[name] = _number(row, name, prefix)
                if row[name] < 0:
                    raise ValueError(f"{prefix}: {name} cannot be negative")
            else:
                row[name] = None
        row["source"] = str(row.get("source") or "user-supplied").strip()[:120]
        key = (row["underlying"], row["option_type"], row["expiry"], row["strike"])
        if key in snapshot:
            raise ValueError(f"{prefix}: duplicate contract {key}")
        snapshot[key] = row
    if len(dates) != 1:
        raise ValueError(f"{label}: all rows must share the same as_of date")
    return dates.pop(), snapshot


def csv_rows(content: str) -> list[dict]:
    """Read a CSV snapshot, rejecting missing headers and malformed rows."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > 3_000_000:
        raise ValueError("CSV must be UTF-8 text smaller than 3 MB")
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff"), newline=""))
    headers = reader.fieldnames or []
    missing = [name for name in FIELDS if name not in headers]
    if missing:
        raise ValueError("CSV missing required columns: " + ", ".join(missing))
    rows = list(reader)
    if any(None in row for row in rows):
        raise ValueError("CSV contains extra fields; check commas and quoting")
    return rows


def explain_csv(start_csv: str, end_csv: str, exception_threshold: float = 500.0) -> dict:
    return explain_portfolio(csv_rows(start_csv), csv_rows(end_csv), exception_threshold)


def _value(row: dict) -> tuple[float, dict]:
    maturity = max(0, (row["expiry"] - row["as_of"]).days) / 365.0
    results = price_european(row["spot"], row["strike"], maturity,
                             row["rate"], row["dividend_yield"], row["volatility"])
    return results[row["option_type"]], results


def _quote_flags(row: dict, label: str) -> list[str]:
    bid, ask = row["bid"], row["ask"]
    flags = []
    if bid is not None and ask is not None:
        if bid > ask:
            flags.append(f"{label}_CROSSED_QUOTE")
        elif row["mark"] < bid - 1e-8 or row["mark"] > ask + 1e-8:
            flags.append(f"{label}_MARK_OUTSIDE_SPREAD")
    return flags


def explain_portfolio(start_rows: list[dict], end_rows: list[dict],
                      exception_threshold: float = 500.0) -> dict[str, Any]:
    """Reconcile observed option P&L to opening Greeks and BSM repricing."""
    threshold = float(exception_threshold)
    if not isfinite(threshold) or threshold < 0:
        raise ValueError("exception_threshold must be finite and nonnegative")
    day0, start = _read_snapshot(start_rows, "start")
    day1, end = _read_snapshot(end_rows, "end")
    if day1 <= day0:
        raise ValueError("end snapshot date must be after start snapshot date")
    if start.keys() != end.keys():
        missing = sorted(start.keys() - end.keys())
        extra = sorted(end.keys() - start.keys())
        raise ValueError(f"Contract universe changed; missing at end={len(missing)}, added at end={len(extra)}. Trades/expiry lifecycle not supported.")
    elapsed = (day1 - day0).days
    totals = {key: 0.0 for key in (*COMPONENTS, "greek_explained", "model_pnl",
                                   "observed_pnl", "unexplained_pnl", "opening_gross_mark",
                                   "closing_gross_mark", "reconciliation_error")}
    positions = []
    exceptions = []
    for key in sorted(start):
        a, b = start[key], end[key]
        if a["expiry"] < day1:
            raise ValueError(f"{key}: option expired before end snapshot; exercise/settlement not modeled")
        if a["quantity"] != b["quantity"] or a["multiplier"] != b["multiplier"]:
            raise ValueError(f"{key}: quantity or contract multiplier changed; trade/corporate action attribution not modeled")
        size = a["quantity"] * a["multiplier"]
        start_model, g = _value(a)
        end_model, _ = _value(b)
        spot_move = b["spot"] - a["spot"]
        vol_move = 100 * (b["volatility"] - a["volatility"])
        rate_move = 100 * (b["rate"] - a["rate"])
        typ = a["option_type"]
        greek_delta = g["delta_call" if typ == "call" else "delta_put"]
        greek_theta = g["theta_call" if typ == "call" else "theta_put"]
        greek_rho = g["rho_call" if typ == "call" else "rho_put"]
        active = all(g[k] is not None for k in ("gamma", "vega")) and all(
            x is not None for x in (greek_delta, greek_theta, greek_rho))
        factor = {
            "delta": (greek_delta or 0.0) * spot_move * size,
            "gamma": 0.5 * (g["gamma"] or 0.0) * spot_move ** 2 * size,
            "vega": (g["vega"] or 0.0) * vol_move * size,
            "theta": (greek_theta or 0.0) * elapsed * size,
            "rho": (greek_rho or 0.0) * rate_move * size,
        }
        # Dividend-yield contribution holds other starting inputs fixed.
        q_only = price_european(a["spot"], a["strike"],
                                (a["expiry"] - day0).days / 365,
                                a["rate"], b["dividend_yield"], a["volatility"])[typ]
        factor["dividend"] = (q_only - start_model) * size
        greek_explained = sum(factor.values())
        observed = (b["mark"] - a["mark"]) * size
        exact_model = (end_model - start_model) * size
        approx_residual = exact_model - greek_explained
        basis_change = observed - exact_model
        unexplained = observed - greek_explained
        reconciliation = observed - (greek_explained + approx_residual + basis_change)
        flags = _quote_flags(a, "START") + _quote_flags(b, "END")
        if not active:
            flags.append("GREEKS_UNAVAILABLE")
        if abs(approx_residual) > threshold:
            flags.append("APPROXIMATION_RESIDUAL")
        if abs(basis_change) > threshold:
            flags.append("MARKET_MODEL_BASIS_CHANGE")
        contract_id = f"{a['underlying']} {a['expiry'].isoformat()} {a['option_type'].upper()} {a['strike']:g}"
        for flag in flags:
            value = (approx_residual if flag == "APPROXIMATION_RESIDUAL" else
                     basis_change if flag == "MARKET_MODEL_BASIS_CHANGE" else None)
            exceptions.append({"contract": contract_id, "code": flag, "amount": value})
        detail = {
            "contract": contract_id, "underlying": a["underlying"],
            "option_type": typ, "expiry": a["expiry"].isoformat(),
            "strike": a["strike"], "quantity": a["quantity"],
            "multiplier": a["multiplier"], "start_mark": a["mark"],
            "end_mark": b["mark"], "start_model": start_model,
            "end_model": end_model, "start_spot": a["spot"], "end_spot": b["spot"],
            "start_volatility": a["volatility"], "end_volatility": b["volatility"],
            "source_start": a["source"], "source_end": b["source"],
            **factor, "greek_explained": greek_explained,
            "model_pnl": exact_model, "observed_pnl": observed,
            "approximation_residual": approx_residual,
            "market_basis_change": basis_change, "unexplained_pnl": unexplained,
            "reconciliation_error": reconciliation,
            "flags": flags,
        }
        positions.append(detail)
        for component in COMPONENTS:
            totals[component] += detail[component]
        for component in ("greek_explained", "model_pnl", "observed_pnl",
                          "unexplained_pnl", "reconciliation_error"):
            totals[component] += detail[component]
        totals["opening_gross_mark"] += abs(a["mark"] * size)
        totals["closing_gross_mark"] += abs(b["mark"] * size)
    if abs(totals["observed_pnl"] - sum(totals[x] for x in COMPONENTS)) > 1e-7 * max(1.0, abs(totals["observed_pnl"])):
        raise ArithmeticError("P&L reconciliation failed")
    return {
        "report_type": "Option Risk Explain / fixed-position P&L attribution",
        "version": "0.2.0", "start_date": day0.isoformat(),
        "end_date": day1.isoformat(), "calendar_days": elapsed,
        "currency": "USD", "exception_threshold": threshold,
        "position_count": len(positions), "exception_count": len(exceptions),
        "totals": totals, "positions": positions, "exceptions": exceptions,
        "methodology": {
            "explain": "Start-of-period BSM Greeks: delta*dS + 0.5*gamma*dS^2 + vega*dIV(vol points) + theta*calendar days + rho*dr(rate points) + isolated dividend-yield repricing.",
            "approximation_residual": "Exact BSM start-to-end repricing less first/second-order attribution, including interactions and higher-order effects.",
            "market_basis_change": "Observed mark-to-market P&L less exact BSM repricing; includes changes in market/model basis and valuation-input differences, not evidence of mispricing.",
            "reconciliation": "Observed P&L = Greek drivers + approximation residual + market/model basis change.",
            "scope": "Unchanged signed contract quantities; European BSM proxy, 365-calendar-day year, continuous dividends, user-supplied USD marks. Excludes trading, settlement, early exercise, fees, FX, funding and corporate actions.",
            "data_control": "Start/end snapshots must have matching contract identity, quantity and multiplier; all data are supplied by user. Threshold is illustrative, not regulatory.",
        },
    }
