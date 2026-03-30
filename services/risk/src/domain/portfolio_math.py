"""Shared portfolio math utilities for the risk service.

Pure domain functions (no I/O) used by both the route layer and
optimal_allocation so every calculation has exactly one implementation.

ANNUALIZATION: All modules use 252 trading days/year (US equity convention).
This is approximate: NYSE has ~252, TASE ~245, LSE ~253. For multi-market
portfolios the error is ~3% on annualized volatility for TASE-heavy
allocations. A more precise approach would count actual trading days per
ticker, but 252 is standard practice and matches PyPortfolioOpt's default.
"""

from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
"""US equity convention. See module docstring for multi-market limitations."""


def prices_from_info(
    tickers: list[str],
    info_by_ticker: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Extract current prices from yfinance info dicts.

    Tries currentPrice first, then falls back through regularMarketPrice,
    navPrice (ETFs), previousClose in order.
    """
    prices: dict[str, float] = {}
    for t in tickers:
        info = info_by_ticker.get(t, {})
        p = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("navPrice")
            or info.get("previousClose")
        )
        if p is not None:
            prices[t] = float(p)
    return prices


def portfolio_weights(
    holdings: dict[str, float],
    prices: dict[str, float],
) -> dict[str, float]:
    """Portfolio weights from shares × price, normalised to sum to 1."""
    values = {t: holdings[t] * prices[t] for t in holdings if t in prices}
    total = sum(values.values())
    if total == 0:
        return {}
    return {t: v / total for t, v in values.items()}


def portfolio_daily_returns(
    returns: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    """Weighted daily SIMPLE return series for the portfolio.

    Converts per-ticker log returns to simple returns (exp(r) - 1) first,
    then takes the weighted sum. This is the correct cross-sectional
    aggregation: the portfolio simple return is exactly Σ(w_i × r_simple_i).

    The previous implementation summed log returns directly (Σ w_i log_r_i),
    which is an O(σ²) approximation. While small for daily data, it introduced
    an unnecessary bias that compounded through downstream conversions
    (VaR, CVaR, Sharpe all converted back to simple via exp()).

    Callers that need log returns should convert: np.log1p(simple_return).
    """
    tickers = [t for t in weights if t in returns.columns]
    if not tickers:
        return pd.Series(0.0, index=returns.index)
    w = np.array([weights[t] for t in tickers])
    simple = np.exp(returns[tickers].values) - 1
    return pd.Series(simple @ w, index=returns.index)


def portfolio_value(
    holdings: dict[str, float],
    prices: dict[str, float],
) -> float:
    """Total market value of all holdings at current prices."""
    return sum(holdings[t] * prices.get(t, 0) for t in holdings)


def annualise_cov(returns: pd.DataFrame, tickers: list[str]) -> np.ndarray:
    """Annualised covariance matrix with Ledoit-Wolf shrinkage via PyPortfolioOpt.

    Uses the same implementation as the portfolio service (CovarianceShrinkage
    with returns_data=True) to ensure MCTR, efficient frontier, and optimization
    all operate against an identical covariance estimate.

    NaN handling: forward-fill gaps of ≤2 days (covers calendar mismatches
    between NYSE and foreign exchanges), then drop rows where any ticker
    still has NaN. This preserves the intersection of trading days without
    fabricating zero-return observations that would bias the covariance.

    INPUT: log returns. See portfolio service compute_covariance for the
    note on passing log returns to PyPortfolioOpt (O(σ⁴) error, immaterial).
    Output is annualised (PyPortfolioOpt scales by 252 internally).
    """
    from pypfopt import risk_models

    valid = [t for t in tickers if t in returns.columns]
    cleaned = returns[valid].ffill(limit=2).dropna(how="any")

    if len(cleaned) < 2 or len(valid) < 2:
        n = max(len(valid), 1)
        return np.zeros((n, n))

    cov: pd.DataFrame = risk_models.CovarianceShrinkage(
        cleaned, returns_data=True
    ).ledoit_wolf()
    return np.asarray(cov)
