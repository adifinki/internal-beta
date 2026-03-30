"""Value at Risk (VaR) and Conditional VaR (CVaR / Expected Shortfall).

VaR: "On any given day, there's a 5% chance you lose at least this much."
CVaR: "On the worst 5% of days, your average loss is this much."

Uses daily returns — these are 1-day risk measures.
Historical method only — no normality assumptions.

INPUT: daily SIMPLE returns (not log returns). The portfolio_daily_returns
function in portfolio_math.py already returns correct simple returns
(Σ w_i × simple_r_i), so no conversion is needed here.
"""

import numpy as np
import pandas as pd


def compute_var(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
) -> float:
    """1-day historical VaR at the given confidence level.

    Returns a negative dollar amount (the loss threshold).
    """
    percentile = 1.0 - confidence  # 0.05 for 95%
    simple_pct = float(np.percentile(portfolio_returns.dropna(), percentile * 100))
    return simple_pct * portfolio_value


def compute_cvar(
    portfolio_returns: pd.Series,
    portfolio_value: float,
    confidence: float = 0.95,
) -> float:
    """1-day Conditional VaR (Expected Shortfall) — average loss beyond VaR.

    More useful than VaR because it describes the severity of the tail.
    Returns a negative dollar amount.
    """
    percentile = 1.0 - confidence
    threshold = float(np.percentile(portfolio_returns.dropna(), percentile * 100))
    # Standard ES (Basel III/IV): E[X | X ≤ VaR], inclusive of the boundary
    tail = portfolio_returns[portfolio_returns <= threshold]
    if tail.empty:
        return threshold * portfolio_value
    return float(tail.mean()) * portfolio_value
