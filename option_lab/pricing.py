"""Black–Scholes–Merton European options with continuous dividend yields.

All rates and volatility are annualized decimal fractions, maturity in years.
Vega and rho are per 1 percentage point, theta per calendar day.
"""
from __future__ import annotations

from math import erf, exp, isfinite, log, pi, sqrt


def _cdf(x: float) -> float:
    return (1.0 + erf(x / sqrt(2.0))) / 2.0


def _pdf(x: float) -> float:
    return exp(-x * x / 2.0) / sqrt(2.0 * pi)


def price_european(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    dividend: float = 0.0,
    volatility: float = 0.25,
) -> dict[str, float | None]:
    """Price European call/put and analytical Greeks. Prices are per share."""
    S, K, T, r, q, v = map(float, (spot, strike, years, rate, dividend, volatility))
    if not all(map(isfinite, (S, K, T, r, q, v))):
        raise ValueError("All inputs must be finite")
    if S < 0 or K <= 0 or T < 0 or v < 0:
        raise ValueError("Spot, maturity and volatility must be nonnegative; strike must be positive")
    undefined = {
        "delta_call": None, "delta_put": None, "gamma": None, "vega": None,
        "theta_call": None, "theta_put": None, "rho_call": None, "rho_put": None,
    }
    if T == 0:
        return {"call": max(0.0, S - K), "put": max(0.0, K - S), **undefined}
    a = S * exp(-q * T)
    b = K * exp(-r * T)
    if S == 0 or v == 0:
        return {"call": max(0.0, a - b), "put": max(0.0, b - a), **undefined}
    root_t = sqrt(T)
    d1 = (log(S / K) + (r - q + v * v / 2) * T) / (v * root_t)
    d2 = d1 - v * root_t
    base_theta = -a * _pdf(d1) * v / (2 * root_t)
    return {
        "call": max(0.0, a * _cdf(d1) - b * _cdf(d2)),
        "put": max(0.0, b * _cdf(-d2) - a * _cdf(-d1)),
        "delta_call": exp(-q * T) * _cdf(d1),
        "delta_put": exp(-q * T) * (_cdf(d1) - 1),
        "gamma": exp(-q * T) * _pdf(d1) / (S * v * root_t),
        "vega": a * _pdf(d1) * root_t / 100,
        "theta_call": (base_theta - r * b * _cdf(d2) + q * a * _cdf(d1)) / 365,
        "theta_put": (base_theta + r * b * _cdf(-d2) - q * a * _cdf(-d1)) / 365,
        "rho_call": K * T * exp(-r * T) * _cdf(d2) / 100,
        "rho_put": -K * T * exp(-r * T) * _cdf(-d2) / 100,
    }
