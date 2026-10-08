"""Yahoo Finance option-chain data adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
import re
from typing import Any

SYMBOL = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9^._-]{0,19}$")
EXPIRY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COLUMNS = ("contractSymbol", "lastTradeDate", "strike", "lastPrice", "bid", "ask",
           "volume", "openInterest", "impliedVolatility", "inTheMoney", "currency")


class MarketDataError(RuntimeError):
    """An upstream request was rejected or produced unusable data."""


def validate_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not SYMBOL.fullmatch(s):
        raise ValueError("Invalid ticker; use a symbol such as SPY, AAPL or BRK-B")
    return s


def _ticker(symbol: str):
    try:
        import yfinance as yf
    except ImportError as exc:
        raise MarketDataError('Yahoo feature requires: pip install -e ".[market]"') from exc
    return yf.Ticker(validate_symbol(symbol))


def _scalar(value: Any) -> Any:
    """Convert NumPy/pandas scalars to safe finite JSON-friendly values."""
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def expirations(symbol: str) -> dict[str, Any]:
    s = validate_symbol(symbol)
    try:
        values = list(_ticker(s).options)
    except Exception as exc:
        raise MarketDataError(f"Yahoo expiry request failed for {s}: {exc}") from exc
    if not values:
        raise MarketDataError(f"Yahoo returned no expiry dates for {s}")
    return {"ticker": s, "expirations": values, "retrieved_at": _time()}


def quote(symbol: str) -> dict[str, Any]:
    s = validate_symbol(symbol)
    try:
        t = _ticker(s)
        last = _scalar(t.fast_info.get("lastPrice") or t.fast_info.get("last_price"))
    except Exception as exc:
        raise MarketDataError(f"Yahoo quote request failed for {s}: {exc}") from exc
    if not isinstance(last, (int, float)) or not isfinite(float(last)):
        raise MarketDataError(f"Yahoo returned no valid last price for {s}")
    try:
        div = _scalar(t.info.get("trailingAnnualDividendYield"))
    except Exception:
        div = None
    return {"ticker": s, "last_price": last, "trailing_annual_dividend_yield": div,
            "retrieved_at": _time(), "data_provider": "Yahoo Finance via yfinance",
            "quote_delayed_or_stale": "possible"}


def _time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def option_chain(symbol: str, expiry: str, side: str = "both") -> dict[str, Any]:
    s = validate_symbol(symbol)
    if not EXPIRY.fullmatch(expiry):
        raise ValueError("Expiry must be YYYY-MM-DD")
    try:
        datetime.strptime(expiry, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc
    if side not in ("both", "calls", "puts"):
        raise ValueError("Side must be both, calls, or puts")
    try:
        t = _ticker(s)
        available = t.options
        if expiry not in available:
            raise ValueError(f"Expiry {expiry} is not listed for {s}")
        raw = t.option_chain(expiry)
    except ValueError:
        raise
    except Exception as exc:
        raise MarketDataError(f"Yahoo option chain failed for {s} {expiry}: {exc}") from exc
    out = {"ticker": s, "expiry": expiry, "retrieved_at": _time(),
           "data_provider": "Yahoo Finance via yfinance"}
    for label in (("calls", "puts") if side == "both" else (side,)):
        frame = getattr(raw, label)
        rows = []
        for record in frame.reindex(columns=COLUMNS).to_dict("records"):
            rows.append({key: _scalar(value) for key, value in record.items()})
        out[label] = rows
        out[label + "_count"] = len(rows)
    return out
